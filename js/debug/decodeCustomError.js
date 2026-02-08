#!/usr/bin/env node
import { ethers } from 'ethers';
import { loadAbiMap } from '../utils.js';

const input = process.argv[2];
if (!input) {
  console.error('Usage: node debug/decodeCustomError.js <revertDataHex>');
  process.exit(2);
}

const data = String(input).trim();
const abi = loadAbiMap();
const interfaces = [
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

function extractNestedRevertData(raw) {
  if (!raw || typeof raw !== 'string' || !/^0x[0-9a-fA-F]{8,}$/.test(raw)) return null;
  try {
    const payload = `0x${raw.slice(10)}`;
    const [inner] = ethers.AbiCoder.defaultAbiCoder().decode(['bytes'], payload);
    if (typeof inner === 'string' && /^0x[0-9a-fA-F]{8,}$/.test(inner) && inner.toLowerCase() !== raw.toLowerCase()) {
      return inner;
    }
  } catch (_) {}
  return null;
}

let found = null;
for (const iface of interfaces) {
  try {
    const decoded = iface.parseError(data);
    if (!decoded) continue;
    const signature = decoded.fragment?.format('sighash') || `${decoded.name}()`;
    const names = (decoded.fragment?.inputs || []).map((i) => i.name).filter(Boolean);
    const args = {};
    for (let i = 0; i < names.length; i++) args[names[i]] = decoded.args?.[i];
    found = { name: decoded.name, signature, args };
    break;
  } catch (_) {}
}

if (!found) {
  const inner = extractNestedRevertData(data);
  if (inner) {
    for (const iface of interfaces) {
      try {
        const decoded = iface.parseError(inner);
        if (!decoded) continue;
        const signature = decoded.fragment?.format('sighash') || `${decoded.name}()`;
        const names = (decoded.fragment?.inputs || []).map((i) => i.name).filter(Boolean);
        const args = {};
        for (let i = 0; i < names.length; i++) args[names[i]] = decoded.args?.[i];
        found = { wrappedBy: data.slice(0, 10), innerRevertData: inner, name: decoded.name, signature, args };
        break;
      } catch (_) {}
    }
  }
}

if (!found) {
  const selector = data.startsWith('0x') ? data.slice(0, 10) : `0x${data.slice(0, 8)}`;
  console.log(JSON.stringify({ selector, signature: null, args: null }, null, 2));
  process.exit(0);
}

console.log(JSON.stringify(found, null, 2));
