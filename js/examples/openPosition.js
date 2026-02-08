import 'dotenv/config';
import { EZManagerSDK } from '../sdk.js';

const POOL_ADDRESS = '0xb2cc224c1c9feE385f8ad6a55b4d94E92359DC59'; // WETH/USDC Aerodrome Example
const OPEN_USDC = '1'; // 1 USDC
const LOWER_PCT = 0.02;
const UPPER_PCT = 0.02;

function printJson(value) {
  console.log(JSON.stringify(value, (_, v) => (typeof v === 'bigint' ? v.toString() : v), 2));
}

const sdk = await EZManagerSDK.fromEnv();
console.log('Opening position...');
const result = await sdk.openPositionByPct({
  poolAddress: POOL_ADDRESS,
  usdcAmount: OPEN_USDC,
  lowerPct: LOWER_PCT,
  upperPct: UPPER_PCT
});
console.log(`Position opened! Tx: ${result.txHash}`);
if (result.positionKey) console.log(`Key: ${result.positionKey}`);

const keyToRead = result.positionKey;
if (!keyToRead) throw new Error('openPositionByPct returned no positionKey; aborting detail lookup.');

try {
  const positionDetails = await sdk.waitForPosition(keyToRead, {
    blockTag: 'latest',
    attempts: 8,
    delayMs: 900
  });
  const details = {
    position: await sdk.getPositionReadable(keyToRead, { blockTag: 'latest' }),
    positionDetails
  };
  console.log('Details:');
  printJson(details);
} catch (err) {
  console.log('position read failed:', String(err));
}
