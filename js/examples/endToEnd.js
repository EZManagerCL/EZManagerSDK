import 'dotenv/config';
import { EZManagerSDK } from '../sdk.js';
import { runOpenPosition } from './openPosition.js';
import { runReadPosition } from './readPosition.js';
import { runAddCollateral } from './addCollateral.js';
import { runRemoveCollateral } from './removeCollateral.js';
import { runCollectFees } from './collectFees.js';
import { runChangeRange } from './changeRange.js';
import { runCompoundFees } from './compoundFees.js';
import { runExitPosition } from './exitPosition.js';

const POOL_ADDRESS = '0xb2cc224c1c9feE385f8ad6a55b4d94E92359DC59'; // WETH/USDC Aerodrome Example
const OPEN_USDC = '10'; // $10 USDC initial position size
const ADD_COLLATERAL_USDC = '2';
const REMOVE_COLLATERAL_USDC = '1';
const OPEN_LOWER_PCT = 0.02;
const OPEN_UPPER_PCT = 0.02;
const NEW_LOWER_PCT = 0.04;
const NEW_UPPER_PCT = 0.04;

// Time to wait before collecting, then before compounding to allow fees to accrue.
// Set higher for smaller positions to test compound/collect.
const WAIT_SECONDS = 120;

// 99% slippage, effectively no slippage protection, lets very small amounts not revert.
const SLIPPAGE_PCT = 0.99;

// Minimum pending fees in USDC to attempt collect or compound
const MIN_PENDING_FEES_USDC = '0.001'; // $0.001

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function pendingFeesUsdc(details) {
  const raw = details?.positionDetails?.pendingFeesUSDC ?? '0';
  return BigInt(String(raw));
}

function usdcToRaw(usdcAmount, decimals = 6) {
  const [wholePart, fracPart = ''] = String(usdcAmount).trim().split('.');
  const whole = wholePart === '' ? '0' : wholePart;
  const frac = `${fracPart}0`.slice(0, decimals);
  return BigInt(`${whole}${frac.padEnd(decimals, '0')}`);
}

const MIN_PENDING_FEES_USDC_RAW = usdcToRaw(MIN_PENDING_FEES_USDC);

const sdk = await EZManagerSDK.fromEnv();

console.log('Step 1: Opening +-2% position with $2 USDC...');
const open = await runOpenPosition({
  sdk,
  poolAddress: POOL_ADDRESS,
  usdcAmount: OPEN_USDC,
  lowerPct: OPEN_LOWER_PCT,
  upperPct: OPEN_UPPER_PCT,
  slippage: SLIPPAGE_PCT,
  readAfter: true
});
const positionKey = open.positionKey;

console.log('Step 2: Add $1 collateral...');
await runAddCollateral({
  sdk,
  key: positionKey,
  usdcAmount: ADD_COLLATERAL_USDC,
  slippage: SLIPPAGE_PCT,
  readAfter: true
});

console.log('Step 3: Remove $1 collateral...');
await runRemoveCollateral({
  sdk,
  key: positionKey,
  usdcAmount: REMOVE_COLLATERAL_USDC,
  slippage: SLIPPAGE_PCT,
  readAfter: true
});

console.log(`Step 4: Wait ${WAIT_SECONDS} seconds before collect...`);
await sleep(WAIT_SECONDS * 1000);
const beforeCollectDetails = await runReadPosition({ sdk, key: positionKey, label: 'after wait before collect' });

console.log('Step 5: Collect fees...');
if (pendingFeesUsdc(beforeCollectDetails) < MIN_PENDING_FEES_USDC_RAW) {
  console.log(
    `Skipping collectFeesToUSDC because pendingFeesUSDC is below $${MIN_PENDING_FEES_USDC}.`
  );
} else {
  await runCollectFees({ sdk, key: positionKey, slippage: SLIPPAGE_PCT, readAfter: true });
}

console.log('Step 6: Change range to +-4%...');
await runChangeRange({
  sdk,
  key: positionKey,
  lowerPct: NEW_LOWER_PCT,
  upperPct: NEW_UPPER_PCT,
  slippage: SLIPPAGE_PCT,
  readAfter: true
});

console.log(`Step 7: Wait ${WAIT_SECONDS} seconds...`);
await sleep(WAIT_SECONDS * 1000);
const beforeCompoundDetails = await runReadPosition({ sdk, key: positionKey, label: 'after wait before compound' });

console.log('Step 8: Compound fees...');
if (pendingFeesUsdc(beforeCompoundDetails) < MIN_PENDING_FEES_USDC_RAW) {
  console.log(
    `Skipping compoundFees because pendingFeesUSDC is below $${MIN_PENDING_FEES_USDC}.`
  );
} else {
  await runCompoundFees({ sdk, key: positionKey, slippage: SLIPPAGE_PCT, readAfter: true });
}

console.log('Step 9: Exit position...');
await runExitPosition({ sdk, key: positionKey, slippage: SLIPPAGE_PCT });

console.log('End-to-end flow complete.');
