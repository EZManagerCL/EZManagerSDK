import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ethers } from 'ethers';

export const BPS = 10_000n;
export const MIN_TICK = -887272;
export const MAX_TICK = 887272;
export const LN_1P0001 = Math.log(1.0001);

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export function loadJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

export function loadAddresses(addressesPath = path.join(__dirname, 'addresses.json'), chainId = null) {
  const parsed = loadJson(addressesPath);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('addresses.json must be a JSON object keyed by chain name');
  }
  if (typeof parsed.CLManager === 'string') {
    throw new Error('Legacy flat addresses.json format is not supported; use chain-name keys (mainnet/base/arbitrum)');
  }

  const chainKey = chainId == null ? 'base' : String(chainId);
  const chainName = chainKey === '1'
    ? 'mainnet'
    : (chainKey === '8453' ? 'base' : (chainKey === '42161' ? 'arbitrum' : chainKey));
  const source = parsed?.chains && typeof parsed.chains === 'object' && !Array.isArray(parsed.chains)
    ? parsed.chains
    : parsed;
  const selected = source?.[chainName] ?? source?.[chainKey] ?? source?.base;
  const selectedIsAddressMap = selected && typeof selected === 'object' && !Array.isArray(selected) && typeof selected.CLManager === 'string';
  if (!selectedIsAddressMap) {
    throw new Error(`addresses.json missing addresses for chain ${chainKey}`);
  }
  return selected;
}

export function loadAbiMap(abiDir = path.join(__dirname, 'abi')) {
  const files = {
    ERC20: 'ERC20.json',
    CL_MANAGER: 'CL_MANAGER.json',
    CL_CORE: 'CL_CORE.json',
    UNI_FACTORY: 'UNI_FACTORY.json',
    SLIP_FACTORY: 'SLIP_FACTORY.json',
    UNI_POOL: 'UNI_POOL.json',
    SLIP_POOL: 'SLIP_POOL.json',
    DEX_ADAPTER: 'DEX_ADAPTER.json',
    REBALANCE_PLANNER: 'REBALANCE_PLANNER.json',
    VALUATION: 'VALUATION.json'
  };

  const abi = {};
  for (const [key, fileName] of Object.entries(files)) {
    const full = path.join(abiDir, fileName);
    const parsed = loadJson(full);
    abi[key] = Array.isArray(parsed) ? parsed : (parsed?.abi ?? []);
  }
  return Object.freeze(abi);
}

export function toBigInt(value) {
  if (typeof value === 'bigint') return value;
  if (typeof value === 'number') return BigInt(Math.trunc(value));
  if (typeof value === 'string') return BigInt(value);
  if (value == null) return 0n;
  if (typeof value.toString === 'function') return BigInt(value.toString());
  throw new Error(`Cannot convert to bigint: ${value}`);
}

export function parseUnits(value, decimals = 18) {
  if (typeof value === 'bigint') return value;
  return ethers.parseUnits(String(value), decimals);
}

export function formatUnits(value, decimals = 18) {
  return ethers.formatUnits(toBigInt(value), decimals);
}

export function formatUSDC(value, decimals = 6) {
  return `${formatUnits(value, decimals)} USDC`;
}

export function sortTokens(a, b) {
  return a.toLowerCase() < b.toLowerCase() ? [a, b] : [b, a];
}

export function isAddress(value) {
  return typeof value === 'string' && /^0x[0-9a-fA-F]{40}$/.test(value);
}

export function normalizeBytes32(value) {
  if (typeof value !== 'string') throw new Error('bytes32 key must be a hex string');
  if (/^0x[0-9a-fA-F]{64}$/.test(value)) return value;
  throw new Error(`Invalid bytes32 key: ${value}`);
}

export function alignTickDown(value, spacing) {
  if (spacing <= 0) throw new Error('alignTickDown: spacing must be positive');
  return Math.floor(value / spacing) * spacing;
}

export function alignTickUp(value, spacing) {
  if (spacing <= 0) throw new Error('alignTickUp: spacing must be positive');
  return Math.ceil(value / spacing) * spacing;
}

export function normalizeTickBounds(lower, upper, spacing) {
  if (!Number.isFinite(lower) || !Number.isFinite(upper)) {
    throw new Error('normalizeTickBounds: non-finite bounds');
  }

  const lo = Math.min(lower, upper);
  const hi = Math.max(lower, upper);

  let snappedLower = alignTickDown(lo, spacing);
  let snappedUpper = alignTickUp(hi, spacing);

  const minAligned = alignTickUp(MIN_TICK, spacing);
  const maxAligned = alignTickDown(MAX_TICK, spacing);

  if (snappedLower < minAligned) snappedLower = minAligned;
  if (snappedUpper > maxAligned) snappedUpper = maxAligned;
  if (snappedUpper <= snappedLower) snappedUpper = snappedLower + spacing;
  if (snappedUpper > maxAligned) throw new Error('normalizeTickBounds: collapsed outside allowed range');

  return { tickLower: snappedLower, tickUpper: snappedUpper };
}

export function tickToPrice(tick, dec0 = 18, dec1 = 6) {
  const base = Math.exp(LN_1P0001 * Number(tick));
  const scale = Math.pow(10, Number(dec0) - Number(dec1));
  return base * scale;
}

export function priceToTick(price, dec0 = 18, dec1 = 6) {
  const p = Number(price);
  if (!Number.isFinite(p) || p <= 0) throw new Error(`Invalid price: ${price}`);
  const scale = Math.pow(10, Number(dec0) - Number(dec1));
  const unscaled = p / scale;
  if (!(unscaled > 0)) throw new Error('Invalid scaled price');
  return Math.round(Math.log(unscaled) / LN_1P0001);
}

export async function getAllowedDexAdapters(coreContract) {
  const list = await coreContract.listAllowedDexes();
  return Array.from(list || []).map((x) => String(x)).filter((x) => isAddress(x) && x !== ethers.ZeroAddress);
}

export async function resolveDexAdapter(provider, abi, coreContract, dexInput) {
  if (!dexInput) throw new Error('resolveDexAdapter: dex input is required');
  if (isAddress(dexInput)) return dexInput;

  const name = String(dexInput).toLowerCase();
  const adapters = await getAllowedDexAdapters(coreContract);
  if (!adapters.length) throw new Error('resolveDexAdapter: no allowed dex adapters configured on core');

  for (const addr of adapters) {
    const adapter = new ethers.Contract(addr, abi.DEX_ADAPTER, provider);
    let isAer = false;
    let isPancake = false;
    try { isAer = Boolean(await adapter.isAerodrome()); } catch (_) {}
    try {
      if (typeof adapter.isPancakeSwap === 'function') isPancake = Boolean(await adapter.isPancakeSwap());
    } catch (_) {}

    if (name === 'aerodrome' && isAer) return addr;
    if ((name === 'pancake' || name === 'pancakeswap') && isPancake) return addr;
    if (name === 'uniswap' && !isAer && !isPancake) return addr;
  }

  throw new Error(`resolveDexAdapter: could not resolve dex by name "${dexInput}" from allowlist`);
}

export async function resolvePoolContext(provider, abi, coreContract, poolAddress) {
  const adapters = await getAllowedDexAdapters(coreContract);
  for (const adapterAddr of adapters) {
    const adapter = new ethers.Contract(adapterAddr, abi.DEX_ADAPTER, provider);
    try {
      const params = await adapter.validateAndGetPoolParams(poolAddress);
      const token0 = params?.token0 ?? params?.[0];
      const token1 = params?.token1 ?? params?.[1];
      const fee = Number(params?.fee ?? params?.[2] ?? 0);
      const tickSpacing = Math.abs(Number(params?.tickSpacing ?? params?.[3] ?? 0));
      if (!isAddress(token0) || !isAddress(token1)) continue;
      let isAerodrome = false;
      try { isAerodrome = Boolean(await adapter.isAerodrome()); } catch (_) {}
      return {
        adapter: adapterAddr,
        adapterContract: adapter,
        token0,
        token1,
        fee,
        tickSpacing,
        isAerodrome
      };
    } catch (_) {
      // try next allowlisted adapter
    }
  }
  throw new Error('resolvePoolContext: no allowlisted dex adapter validated this pool');
}

export async function getPoolAddress({ provider, abi, coreContract, tokenA, tokenB, poolParam, dex }) {
  const dexAdapter = await resolveDexAdapter(provider, abi, coreContract, dex);
  const adapter = new ethers.Contract(dexAdapter, abi.DEX_ADAPTER, provider);
  const factory = await adapter.getFactory();
  if (!factory || factory === ethers.ZeroAddress) throw new Error('getPoolAddress: adapter factory unavailable');

  const [token0, token1] = sortTokens(tokenA, tokenB);
  let isAer = false;
  try { isAer = Boolean(await adapter.isAerodrome()); } catch (_) {}

  if (isAer) {
    const spacing = Math.abs(Number(poolParam));
    const slipFactory = new ethers.Contract(factory, abi.SLIP_FACTORY, provider);
    const pool = await slipFactory.getPool(token0, token1, spacing);
    if (!pool || pool === ethers.ZeroAddress) throw new Error('getPoolAddress: slipstream pool not found');
    return pool;
  }

  const fee = Number(poolParam);
  const uniFactory = new ethers.Contract(factory, abi.UNI_FACTORY, provider);
  const pool = await uniFactory.getPool(token0, token1, fee);
  if (!pool || pool === ethers.ZeroAddress) throw new Error('getPoolAddress: pool not found');
  return pool;
}

export async function computeRangeFromPct(poolContract, rangePct, spacingOverride = null) {
  const pct = Number(rangePct);
  if (!(pct > 0 && pct < 1)) throw new Error(`computeRangeFromPct: rangePct must be in (0,1), got ${rangePct}`);

  const slot0 = await poolContract.slot0();
  const currentTick = Number(slot0.tick);
  let spacing = spacingOverride == null ? Math.abs(Number(await poolContract.tickSpacing())) : Math.abs(Number(spacingOverride));
  if (!spacing || spacing <= 0) throw new Error('computeRangeFromPct: invalid tick spacing');

  const lowerRaw = currentTick + Math.log(1 - pct) / LN_1P0001;
  const upperRaw = currentTick + Math.log(1 + pct) / LN_1P0001;
  const normalized = normalizeTickBounds(lowerRaw, upperRaw, spacing);

  return {
    tickLower: normalized.tickLower,
    tickUpper: normalized.tickUpper,
    currentTick,
    spacing
  };
}

export async function getTokenDecimals(provider, abi, tokenAddress, fallback = 18) {
  const c = new ethers.Contract(tokenAddress, abi.ERC20, provider);
  try {
    return Number(await c.decimals());
  } catch (_) {
    return fallback;
  }
}

export async function ticksFromPrices({ provider, abi, token0, token1, tickSpacing, priceLower, priceUpper }) {
  const pLo = Number(priceLower);
  const pHi = Number(priceUpper);
  if (!Number.isFinite(pLo) || !Number.isFinite(pHi) || pLo <= 0 || pHi <= 0) {
    throw new Error('ticksFromPrices: priceLower and priceUpper must be positive numbers');
  }

  const dec0 = await getTokenDecimals(provider, abi, token0);
  const dec1 = await getTokenDecimals(provider, abi, token1);
  const lo = Math.min(pLo, pHi);
  const hi = Math.max(pLo, pHi);

  const tickLowerApprox = priceToTick(lo, dec0, dec1);
  const tickUpperApprox = priceToTick(hi, dec0, dec1);
  return normalizeTickBounds(tickLowerApprox, tickUpperApprox, tickSpacing);
}

export function toSlippageBps(slippage) {
  if (slippage == null) return 50;
  const n = Number(slippage);
  if (!Number.isFinite(n)) throw new Error(`Invalid slippage: ${slippage}`);
  if (n > 1) return Math.round(n);
  if (n <= 0) throw new Error('Slippage must be > 0');
  return Math.round(n * 10_000);
}
