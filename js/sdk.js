import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ethers } from 'ethers';
import 'dotenv/config';
import {
  loadAbiMap,
  loadAddresses,
  toBigInt,
  parseUnits,
  LN_1P0001,
  normalizeTickBounds,
  toSlippageBps,
  normalizeBytes32,
  resolveDexAdapter,
  resolvePoolContext,
  getPoolAddress,
  ticksFromPrices
} from './utils.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export class EZManagerSDK {
  constructor({ provider, signer, addresses, abi, manager, core, usdc, valuation }) {
    this.provider = provider;
    this.signer = signer;
    this.addresses = addresses;
    this.abi = abi;
    this.manager = manager;
    this.core = core;
    this.usdc = usdc;
    this.valuation = valuation;
    this._errorInterfaces = [
      new ethers.Interface(['error Error(string)', 'error Panic(uint256)']),
      new ethers.Interface(abi.CL_MANAGER),
      new ethers.Interface(abi.CL_CORE),
      new ethers.Interface(abi.DEX_ADAPTER),
      new ethers.Interface(abi.REBALANCE_PLANNER),
      new ethers.Interface(abi.VALUATION),
      new ethers.Interface(abi.ERC20),
      new ethers.Interface(abi.UNI_FACTORY),
      new ethers.Interface(abi.SLIP_FACTORY),
      new ethers.Interface(abi.UNI_POOL),
      new ethers.Interface(abi.SLIP_POOL)
    ];
    this._eventInterfaces = Object.fromEntries(
      Object.entries(abi).map(([key, value]) => [key, new ethers.Interface(value)])
    );
    this._gasBufferBps = this._readEnvInt('TX_GAS_BUFFER_BPS', 2000);
    this._gasBufferMin = BigInt(this._readEnvInt('TX_GAS_BUFFER_MIN', 50000));
  }

  _readEnvInt(name, fallback) {
    const raw = process.env[name];
    if (raw == null || raw === '') return fallback;
    const value = Number(raw);
    if (!Number.isFinite(value)) return fallback;
    return Math.max(0, Math.floor(value));
  }

  _formatTxHash(value) {
    if (value == null) return '';
    const s = String(value).trim().toLowerCase();
    if (!s) return '';
    return s.startsWith('0x') ? s : `0x${s}`;
  }

  static async fromEnv({
    rpcUrl = process.env.RPC_URL,
    privateKey = process.env.PRIVATE_KEY,
    addressesPath = path.join(__dirname, 'addresses.json'),
    abiDir = path.join(__dirname, 'abi')
  } = {}) {
    if (!rpcUrl) throw new Error('RPC_URL is required');
    if (!privateKey) throw new Error('PRIVATE_KEY is required');

    const abi = loadAbiMap(abiDir);
    const addresses = loadAddresses(addressesPath);
    if (!addresses.CLManager) {
      throw new Error('addresses.json missing CLManager');
    }

    const provider = new ethers.JsonRpcProvider(rpcUrl);
    const signer = new ethers.Wallet(privateKey, provider);
    const manager = new ethers.Contract(addresses.CLManager, abi.CL_MANAGER, signer);
    const coreAddress = await manager.CORE();
    const core = new ethers.Contract(coreAddress, abi.CL_CORE, signer);

    const usdcAddress = await manager.USDC();
    const usdc = new ethers.Contract(usdcAddress, abi.ERC20, signer);

    let valuation = null;
    if (addresses.Valuation) {
      valuation = new ethers.Contract(addresses.Valuation, abi.VALUATION, provider);
    }

    return new EZManagerSDK({ provider, signer, addresses, abi, manager, core, usdc, valuation });
  }

  // Low-level generic access so advanced users are never blocked by wrapper coverage.
  async callManager(method, ...args) {
    if (typeof this.manager[method] !== 'function') throw new Error(`Unknown manager method: ${method}`);
    return this.manager[method](...args);
  }

  async sendManager(method, ...args) {
    if (typeof this.manager[method] !== 'function') throw new Error(`Unknown manager method: ${method}`);
    return (await this._sendContractTx(this.manager, method, args)).receipt;
  }

  async callCore(method, ...args) {
    if (typeof this.core[method] !== 'function') throw new Error(`Unknown core method: ${method}`);
    return this.core[method](...args);
  }

  async sendCore(method, ...args) {
    if (typeof this.core[method] !== 'function') throw new Error(`Unknown core method: ${method}`);
    return (await this._sendContractTx(this.core, method, args)).receipt;
  }

  _extractRevertData(error) {
    const stack = [error, error?.data, error?.error, error?.info, error?.cause];
    while (stack.length) {
      const cur = stack.shift();
      if (!cur) continue;
      if (typeof cur === 'string' && /^0x[0-9a-fA-F]{8,}$/.test(cur)) return cur;
      if (Array.isArray(cur)) {
        for (const x of cur) stack.push(x);
        continue;
      }
      if (typeof cur === 'object') {
        for (const key of ['data', 'error', 'result', 'revert', 'message']) {
          if (cur[key] != null) stack.push(cur[key]);
        }
      }
    }
    return null;
  }

  decodeCustomError(data) {
    if (!data || typeof data !== 'string' || !data.startsWith('0x')) return null;
    for (const iface of this._errorInterfaces) {
      try {
        const decoded = iface.parseError(data);
        if (!decoded) continue;
        const signature = decoded.fragment?.format('sighash') || `${decoded.name}()`;
        const args = {};
        const inputs = decoded.fragment?.inputs || [];
        for (let i = 0; i < inputs.length; i++) {
          const name = inputs[i]?.name || `arg${i}`;
          args[name] = decoded.args?.[i];
        }
        return { name: decoded.name, signature, args };
      } catch (_) {}
    }
    return null;
  }

  _extractNestedRevertData(data) {
    if (!data || typeof data !== 'string' || !/^0x[0-9a-fA-F]{8,}$/.test(data)) return null;
    try {
      const payload = `0x${data.slice(10)}`;
      const [inner] = ethers.AbiCoder.defaultAbiCoder().decode(['bytes'], payload);
      if (typeof inner === 'string' && /^0x[0-9a-fA-F]{8,}$/.test(inner) && inner.toLowerCase() !== data.toLowerCase()) {
        return inner;
      }
    } catch (_) {}
    return null;
  }

  _augmentError(error) {
    const data = this._extractRevertData(error);
    const decoded = this.decodeCustomError(data);
    let innerData = null;
    let innerDecoded = null;
    if (!decoded) {
      innerData = this._extractNestedRevertData(data);
      innerDecoded = this.decodeCustomError(innerData);
    }
    if (!decoded && !innerDecoded) {
      if (!data) return error;
      const unknown = new Error(`Transaction reverted with unknown custom error selector ${data.slice(0, 10)}`);
      unknown.cause = error;
      unknown.revertData = data;
      return unknown;
    }
    const active = decoded || innerDecoded;
    const details = Object.keys(active.args || {}).length ? ` args=${JSON.stringify(active.args)}` : '';
    const msg = decoded
      ? `Transaction reverted with custom error ${active.signature}${details}`
      : `Transaction reverted with wrapped custom error selector ${data.slice(0, 10)} inner=${active.signature}${details}`;
    const wrapped = new Error(msg);
    wrapped.cause = error;
    wrapped.revertData = data;
    if (innerData) wrapped.innerRevertData = innerData;
    wrapped.decodedCustomError = active;
    return wrapped;
  }

  _withGasBuffer(estimatedGas) {
    const est = toBigInt(estimatedGas);
    const buffered = est + ((est * BigInt(this._gasBufferBps)) / 10000n);
    return buffered + this._gasBufferMin;
  }

  async _sendContractTx(contract, method, args = [], overrides = {}) {
    const fn = contract?.getFunction?.(method);
    if (!fn) throw new Error(`Unknown contract method: ${method}`);
    const txReq = await fn.populateTransaction(...args, overrides);
    if (txReq.to == null) txReq.to = contract.target;
    if (txReq.from == null) txReq.from = this.signer.address;
    const callerProvidedGas = overrides?.gasLimit != null || overrides?.gas != null;
    if (!callerProvidedGas) {
      try {
        const estimateReq = { ...txReq };
        delete estimateReq.gasLimit;
        delete estimateReq.gas;
        const estimated = await this.provider.estimateGas(estimateReq);
        txReq.gasLimit = this._withGasBuffer(estimated);
      } catch (error) {
        throw this._augmentError(error);
      }
    }
    return this._sendTx(() => this.signer.sendTransaction(txReq));
  }

  _flattenTraceFailures(node, path = 'root', out = []) {
    if (!node || typeof node !== 'object') return out;
    if (node.error) {
      out.push({
        path,
        error: String(node.error),
        output: typeof node.output === 'string' ? node.output : null,
        to: node.to ?? null,
        from: node.from ?? null,
        type: node.type ?? null
      });
    }
    if (Array.isArray(node.calls)) {
      for (let i = 0; i < node.calls.length; i++) {
        this._flattenTraceFailures(node.calls[i], `${path}.calls[${i}]`, out);
      }
    }
    return out;
  }

  _pathsRelated(a, b) {
    if (!a || !b) return false;
    return a === b || a.startsWith(`${b}.`) || b.startsWith(`${a}.`);
  }

  async _traceFailureSummary(txHash) {
    if (!txHash) return null;
    try {
      const trace = await this.provider.send('debug_traceTransaction', [txHash, { tracer: 'callTracer' }]);
      const failures = this._flattenTraceFailures(trace);
      const outOfGasFailures = failures.filter((f) => /out of gas/i.test(f.error || ''));
      const outOfGas = outOfGasFailures.length > 0;
      const terminalFailure = failures.length ? failures[failures.length - 1] : null;
      const withOutput = [...failures].reverse().find((f) => {
        if (!(typeof f.output === 'string' && /^0x[0-9a-fA-F]{8,}$/.test(f.output))) return false;
        if (!terminalFailure) return true;
        return this._pathsRelated(f.path, terminalFailure.path);
      }) || [...failures].reverse().find((f) => typeof f.output === 'string' && /^0x[0-9a-fA-F]{8,}$/.test(f.output));
      const decoded = withOutput ? this.decodeCustomError(withOutput.output) : null;
      return { failures, outOfGas, withOutput, decoded, terminalFailure };
    } catch (_) {
      return null;
    }
  }

  _statusZeroErrorMessage({ txHash, reason, gasUsed, gasLimit, outOfGas }) {
    const parts = [`Transaction failed on-chain (status=0). txHash=${this._formatTxHash(txHash)}`];
    if (reason) parts.push(`reason=${reason}`);
    if (outOfGas) parts.push('rootCause=out-of-gas');
    if (gasUsed != null || gasLimit != null) parts.push(`gasUsed=${gasUsed ?? 'unknown'} gasLimit=${gasLimit ?? 'unknown'}`);
    return parts.join(' ');
  }

  async _buildStatusZeroError({ txHash, tx = null, receipt = null, originalError = null }) {
    txHash = this._formatTxHash(txHash);
    const onchainTx = tx || (txHash ? await this.provider.getTransaction(txHash).catch(() => null) : null);
    const onchainReceipt = receipt || (txHash ? await this.provider.getTransactionReceipt(txHash).catch(() => null) : null);
    let reason = null;
    let reasonCause = null;

    if (onchainTx) {
      const callTx = {
        from: onchainTx.from ?? onchainTx.fromAddress ?? this.signer.address,
        to: onchainTx.to ?? null,
        data: onchainTx.data ?? '0x',
        value: onchainTx.value ?? 0n
      };
      try {
        await this.provider.call(callTx, onchainReceipt?.blockNumber ?? 'latest');
      } catch (simError) {
        const augmented = this._augmentError(simError);
        reason = augmented.message || String(augmented);
        reasonCause = augmented;
      }
    }

    const traceSummary = await this._traceFailureSummary(txHash);
    const outOfGas = Boolean(traceSummary?.outOfGas);
    const terminalFailure = traceSummary?.terminalFailure || null;
    const decodedRelatedToTerminal = traceSummary?.withOutput && terminalFailure
      ? this._pathsRelated(traceSummary.withOutput.path, terminalFailure.path)
      : false;
    if (!reason && traceSummary?.decoded?.signature && (!outOfGas || decodedRelatedToTerminal)) {
      const args = traceSummary.decoded.args || {};
      const details = Object.keys(args).length ? ` args=${JSON.stringify(args)}` : '';
      reason = `${traceSummary.decoded.signature}${details}`;
    } else if (!reason && traceSummary?.withOutput && (!outOfGas || decodedRelatedToTerminal)) {
      reason = `revertData=${traceSummary.withOutput.output}`;
    } else if (!reason && originalError) {
      reason = originalError?.shortMessage || originalError?.message || String(originalError);
    }
    if (outOfGas && (!reason || !/out of gas/i.test(reason))) {
      reason = reason ? `${reason}; execution trace reports out of gas` : 'execution trace reports out of gas';
    }

    const gasUsed = onchainReceipt?.gasUsed != null ? String(onchainReceipt.gasUsed) : null;
    const gasLimitValue = onchainTx?.gasLimit ?? tx?.gasLimit ?? null;
    const gasLimit = gasLimitValue != null ? String(gasLimitValue) : null;
    const wrapped = new Error(
      this._statusZeroErrorMessage({
        txHash,
        reason,
        gasUsed,
        gasLimit,
        outOfGas
      })
    );
    wrapped.cause = reasonCause || originalError || null;
    wrapped.txHash = this._formatTxHash(txHash);
    wrapped.receipt = onchainReceipt || null;
    wrapped.outOfGas = outOfGas;
    wrapped.traceFailures = traceSummary?.failures || null;
    wrapped.reason = reason;
    return wrapped;
  }

  async _sendTx(makeTx) {
    let tx = null;
    try {
      tx = await makeTx();
      const receipt = await tx.wait();
      if (Number(receipt?.status ?? 0) !== 1) {
        throw await this._buildStatusZeroError({ txHash: tx.hash, tx, receipt });
      }
      return { tx, receipt };
    } catch (error) {
      const txHash = this._formatTxHash(tx?.hash || error?.transactionHash || error?.receipt?.hash || error?.receipt?.transactionHash);
      if (txHash) {
        const receipt = error?.receipt || (await this.provider.getTransactionReceipt(txHash).catch(() => null));
        if (Number(receipt?.status ?? 1) === 0) {
          throw await this._buildStatusZeroError({ txHash, tx, receipt, originalError: error });
        }
      }
      throw this._augmentError(error);
    }
  }

  async _sleep(ms) {
    await new Promise((resolve) => setTimeout(resolve, Math.max(0, Number(ms) || 0)));
  }

  _normalizeReadableValue(value) {
    if (typeof value === 'bigint') return value.toString();
    if (value instanceof Uint8Array) return ethers.hexlify(value);
    if (Array.isArray(value)) return value.map((v) => this._normalizeReadableValue(v));
    if (value && typeof value === 'object') {
      const out = {};
      for (const [k, v] of Object.entries(value)) out[k] = this._normalizeReadableValue(v);
      return out;
    }
    return value;
  }

  _getCoreStructFieldNames(functionName) {
    for (const item of this.abi.CL_CORE || []) {
      if (!item || item.type !== 'function' || item.name !== functionName) continue;
      const outputs = item.outputs || [];
      if (!outputs.length) return null;
      const components = outputs[0].components || [];
      if (!components.length) return null;
      return components.map((c, idx) => c?.name || `field_${idx}`);
    }
    return null;
  }

  _structToReadableObject(functionName, value) {
    const names = this._getCoreStructFieldNames(functionName);
    if (!names || !value) return this._normalizeReadableValue(value);
    const out = {};
    for (const name of names) out[name] = this._normalizeReadableValue(value[name]);
    return out;
  }

  extractOpenedKeyFromReceipt(receipt) {
    const events = this.decodeReceiptEvents({
      receipt,
      abiKey: 'CL_MANAGER',
      eventName: 'PositionOpened',
      address: this.addresses.CLManager
    });
    for (const evt of events) {
      const key = evt?.args?.key;
      if (key != null) return normalizeBytes32(key);
    }
    return null;
  }

  decodeReceiptEvents({ receipt, abiKey, eventName = null, address = null }) {
    const iface = this._eventInterfaces[abiKey];
    if (!iface) throw new Error(`Unknown abiKey for events: ${abiKey}`);
    const normalizedAddr = address ? String(address).toLowerCase() : null;
    const out = [];
    for (const log of receipt?.logs ?? []) {
      if (!log?.topics?.length) continue;
      if (normalizedAddr && String(log.address || '').toLowerCase() !== normalizedAddr) continue;
      try {
        const decoded = iface.parseLog(log);
        if (!decoded) continue;
        if (eventName && decoded.name !== eventName) continue;
        const args = {};
        for (const input of decoded.fragment.inputs || []) {
          if (input?.name) args[input.name] = decoded.args?.[input.name];
        }
        out.push({ event: decoded.name, args, log, decoded });
      } catch (_) {}
    }
    return out;
  }

  async usdcDecimals() {
    try {
      return Number(await this.usdc.decimals());
    } catch (_) {
      return 6;
    }
  }

  async ensureUsdcAllowance(spender, minAmount) {
    const required = toBigInt(minAmount);
    const spenderAddr = ethers.getAddress(spender);
    const allowance = await this.usdc.allowance(this.signer.address, spenderAddr);
    if (allowance >= required) return null;
    const max = (2n ** 256n) - 1n;
    try {
      await this._sendContractTx(this.usdc, 'approve', [spenderAddr, max]);
    } catch (_) {
      await this._sendContractTx(this.usdc, 'approve', [spenderAddr, 0n]);
      await this._sendContractTx(this.usdc, 'approve', [spenderAddr, max]);
    }
    const finalAllowance = await this.usdc.allowance(this.signer.address, spenderAddr);
    if (finalAllowance < required) {
      throw new Error(
        `USDC allowance insufficient after approve. required=${required.toString()} actual=${finalAllowance.toString()} spender=${spenderAddr}`
      );
    }
    return null;
  }

  async resolveDexAdapter(dex) {
    return resolveDexAdapter(this.provider, this.abi, this.core, dex);
  }

  async getPoolAddress({ tokenA, tokenB, poolParam, dex }) {
    return getPoolAddress({
      provider: this.provider,
      abi: this.abi,
      coreContract: this.core,
      tokenA,
      tokenB,
      poolParam,
      dex
    });
  }

  async openPosition({ poolAddress, tickLower, tickUpper, usdcAmount, slippageBps = 50 }) {
    if (!poolAddress) throw new Error('openPosition: poolAddress required');
    if (tickLower == null || tickUpper == null) throw new Error('openPosition: tickLower and tickUpper required');
    if (usdcAmount == null) throw new Error('openPosition: usdcAmount required');

    const amountRaw = parseUnits(String(usdcAmount), await this.usdcDecimals());
    await this.ensureUsdcAllowance(this.addresses.CLManager, amountRaw);

    const { tx, receipt } = await this._sendContractTx(
      this.manager,
      'openPosition',
      [poolAddress, Number(tickLower), Number(tickUpper), amountRaw, Number(slippageBps)]
    );
    return { txHash: this._formatTxHash(tx.hash), receipt, positionKey: this.extractOpenedKeyFromReceipt(receipt) };
  }

  async openPositionByPct({ poolAddress, usdcAmount, lowerPct, upperPct, rangePct, slippage = 0.005 }) {
    if (rangePct != null && (lowerPct == null && upperPct == null)) {
      lowerPct = Number(rangePct);
      upperPct = Number(rangePct);
    }
    if (!(Number(lowerPct) > 0 && Number(lowerPct) < 1)) throw new Error('openPositionByPct: lowerPct must be in (0,1)');
    if (!(Number(upperPct) > 0 && Number(upperPct) < 1)) throw new Error('openPositionByPct: upperPct must be in (0,1)');

    const ctx = await resolvePoolContext(this.provider, this.abi, this.core, poolAddress);
    const poolAbi = ctx.isAerodrome ? this.abi.SLIP_POOL : this.abi.UNI_POOL;
    const pool = new ethers.Contract(poolAddress, poolAbi, this.provider);
    const slot0 = await pool.slot0();
    const currentTick = Number(slot0.tick);
    const tickSpacing = ctx.tickSpacing || 1;
    const lowerRaw = currentTick + Math.log(1 - Number(lowerPct)) / LN_1P0001;
    const upperRaw = currentTick + Math.log(1 + Number(upperPct)) / LN_1P0001;
    const range = normalizeTickBounds(lowerRaw, upperRaw, tickSpacing);

    return this.openPosition({
      poolAddress,
      tickLower: range.tickLower,
      tickUpper: range.tickUpper,
      usdcAmount,
      slippageBps: toSlippageBps(slippage)
    });
  }

  async openPositionByPrice({ poolAddress, priceLower, priceUpper, usdcAmount, slippage = 0.005 }) {
    const ctx = await resolvePoolContext(this.provider, this.abi, this.core, poolAddress);
    const ticks = await ticksFromPrices({
      provider: this.provider,
      abi: this.abi,
      token0: ctx.token0,
      token1: ctx.token1,
      tickSpacing: ctx.tickSpacing,
      priceLower,
      priceUpper
    });

    return this.openPosition({
      poolAddress,
      tickLower: ticks.tickLower,
      tickUpper: ticks.tickUpper,
      usdcAmount,
      slippageBps: toSlippageBps(slippage)
    });
  }

  async addCollateral({ key, usdcAmount, slippage = 0.005 }) {
    const amountRaw = parseUnits(String(usdcAmount), await this.usdcDecimals());
    const normalizedKey = normalizeBytes32(key);
    await this.ensureUsdcAllowance(this.addresses.CLManager, amountRaw);
    const { tx, receipt } = await this._sendContractTx(
      this.manager,
      'addCollateral',
      [normalizedKey, amountRaw, toSlippageBps(slippage)]
    );
    return { txHash: this._formatTxHash(tx.hash), receipt };
  }

  async removeCollateral({ key, usdcAmount, slippage = 0.005 }) {
    const amountRaw = parseUnits(String(usdcAmount), await this.usdcDecimals());
    const normalizedKey = normalizeBytes32(key);
    const { tx, receipt } = await this._sendContractTx(
      this.manager,
      'removeCollateral',
      [normalizedKey, amountRaw, toSlippageBps(slippage)]
    );
    return { txHash: this._formatTxHash(tx.hash), receipt };
  }

  async changeRange({ key, tickLower, tickUpper, slippage = 0.005 }) {
    const normalizedKey = normalizeBytes32(key);
    if (tickLower == null || tickUpper == null) throw new Error('changeRange: tickLower and tickUpper required');
    const { tx, receipt } = await this._sendContractTx(
      this.manager,
      'changeRange',
      [normalizedKey, Number(tickLower), Number(tickUpper), toSlippageBps(slippage)]
    );
    return { txHash: this._formatTxHash(tx.hash), receipt };
  }

  async changeRangeByPct({ key, lowerPct, upperPct, slippage = 0.005 }) {
    if (!(Number(lowerPct) > 0 && Number(lowerPct) < 1)) throw new Error('changeRangeByPct: lowerPct must be in (0,1)');
    if (!(Number(upperPct) > 0 && Number(upperPct) < 1)) throw new Error('changeRangeByPct: upperPct must be in (0,1)');
    const normalizedKey = normalizeBytes32(key);
    const details = await this.core.getPositionDetails(normalizedKey);
    const position = await this.core.getPosition(normalizedKey);
    const dex = position.dex;
    const adapter = new ethers.Contract(dex, this.abi.DEX_ADAPTER, this.provider);
    let isAerodrome = false;
    try { isAerodrome = Boolean(await adapter.isAerodrome()); } catch (_) {}

    const tickSpacing = Math.abs(Number(details.tickSpacing));
    const poolParam = isAerodrome ? tickSpacing : Number(details.fee);
    const poolAddress = await this.getPoolAddress({ tokenA: details.token0, tokenB: details.token1, poolParam, dex });
    const poolAbi = isAerodrome ? this.abi.SLIP_POOL : this.abi.UNI_POOL;
    const pool = new ethers.Contract(poolAddress, poolAbi, this.provider);
    const slot0 = await pool.slot0();
    const currentTick = Number(slot0.tick);
    const lowerRaw = currentTick + Math.log(1 - Number(lowerPct)) / LN_1P0001;
    const upperRaw = currentTick + Math.log(1 + Number(upperPct)) / LN_1P0001;
    const snapped = normalizeTickBounds(lowerRaw, upperRaw, tickSpacing || 1);
    return this.changeRange({ key: normalizedKey, tickLower: snapped.tickLower, tickUpper: snapped.tickUpper, slippage });
  }

  async changeRangeByPrice({ key, priceLower, priceUpper, slippage = 0.005 }) {
    const normalizedKey = normalizeBytes32(key);
    const details = await this.core.getPositionDetails(normalizedKey);
    const tickSpacing = Math.abs(Number(details.tickSpacing));
    const ticks = await ticksFromPrices({
      provider: this.provider,
      abi: this.abi,
      token0: details.token0,
      token1: details.token1,
      tickSpacing,
      priceLower,
      priceUpper
    });

    return this.changeRange({
      key: normalizedKey,
      tickLower: ticks.tickLower,
      tickUpper: ticks.tickUpper,
      slippage
    });
  }

  async collectFeesToUSDC({ keys, slippage = 0.005 }) {
    const keyList = (Array.isArray(keys) ? keys : [keys]).map((k) => normalizeBytes32(k));
    const { tx, receipt } = await this._sendContractTx(
      this.manager,
      'collectFeesToUSDC',
      [keyList, toSlippageBps(slippage)]
    );
    return { txHash: this._formatTxHash(tx.hash), receipt };
  }

  async compoundFees({ keys, slippage = 0.005 }) {
    const keyList = (Array.isArray(keys) ? keys : [keys]).map((k) => normalizeBytes32(k));
    const { tx, receipt } = await this._sendContractTx(
      this.manager,
      'compoundFees',
      [keyList, toSlippageBps(slippage)]
    );
    return { txHash: this._formatTxHash(tx.hash), receipt };
  }

  async exitPosition({ keys, slippage = 0.005 }) {
    const keyList = (Array.isArray(keys) ? keys : [keys]).map((k) => normalizeBytes32(k));
    const { tx, receipt } = await this._sendContractTx(
      this.manager,
      'exitPosition',
      [keyList, toSlippageBps(slippage)]
    );
    return { txHash: this._formatTxHash(tx.hash), receipt };
  }

  async allowBotForPosition({ key, allowed = true }) {
    const { tx, receipt } = await this._sendContractTx(
      this.manager,
      'allowBotForPosition',
      [normalizeBytes32(key), Boolean(allowed)]
    );
    return { txHash: this._formatTxHash(tx.hash), receipt };
  }

  async withdrawDust({ key }) {
    const { tx, receipt } = await this._sendContractTx(this.manager, 'withdrawDust', [normalizeBytes32(key)]);
    return { txHash: this._formatTxHash(tx.hash), receipt };
  }

  async returnNft({ keys }) {
    const keyList = (Array.isArray(keys) ? keys : [keys]).map((k) => normalizeBytes32(k));
    const { tx, receipt } = await this._sendContractTx(this.manager, 'returnNft', [keyList]);
    return { txHash: this._formatTxHash(tx.hash), receipt };
  }

  async getUserPositionKeys(user = this.signer.address, { blockTag = 'latest' } = {}) {
    return this.core.listUserPositionKeys(user, { blockTag });
  }

  async getUserPositionDetailsReadable(user = this.signer.address, { blockTag = 'latest' } = {}) {
    const keys = await this.getUserPositionKeys(user, { blockTag });
    const out = [];
    for (const key of keys || []) {
      const normalizedKey = normalizeBytes32(key);
      const positionDetails = await this.getPositionDetailsReadable(normalizedKey, { blockTag });
      out.push({ key: normalizedKey, positionDetails });
    }
    return out;
  }

  async getPosition(key, { blockTag = 'latest' } = {}) {
    return this.core.getPosition(normalizeBytes32(key), { blockTag });
  }

  async getPositionDetails(key, { blockTag = 'latest' } = {}) {
    return this.core.getPositionDetails(normalizeBytes32(key), { blockTag });
  }

  async waitForPosition(key, { attempts = 6, delayMs = 800, blockTag = 'latest' } = {}) {
    let lastErr = null;
    for (let i = 0; i < Math.max(1, Number(attempts) || 1); i++) {
      try {
        return await this.getPositionDetailsReadable(key, { blockTag });
      } catch (err) {
        lastErr = err;
        await this._sleep(delayMs);
      }
    }
    throw lastErr || new Error('waitForPosition failed');
  }

  async getPositionReadable(key, { blockTag = 'latest' } = {}) {
    const raw = await this.getPosition(key, { blockTag });
    return this._structToReadableObject('getPosition', raw);
  }

  async getPositionDetailsReadable(key, { blockTag = 'latest' } = {}) {
    const raw = await this.getPositionDetails(key, { blockTag });
    return this._structToReadableObject('getPositionDetails', raw);
  }

  async walletUsdcBalance() {
    return toBigInt(await this.usdc.balanceOf(this.signer.address));
  }

  async valuationUsdc(dex, token, amountRaw) {
    if (!this.valuation) throw new Error('Valuation contract not configured');
    const dexAddr = await this.resolveDexAdapter(dex);
    return toBigInt(await this.valuation.usdcValue(dexAddr, token, toBigInt(amountRaw)));
  }

}

export default EZManagerSDK;
