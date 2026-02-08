import 'dotenv/config';
import { EZManagerSDK } from '../sdk.js';

const POSITION_KEY = '';
const LOWER_PCT = 0.04;
const UPPER_PCT = 0.03;

function printJson(value) {
  console.log(JSON.stringify(value, (_, v) => (typeof v === 'bigint' ? v.toString() : v), 2));
}

const sdk = await EZManagerSDK.fromEnv();
console.log('Changing range...');
const result = await sdk.changeRangeByPct({ key: POSITION_KEY, lowerPct: LOWER_PCT, upperPct: UPPER_PCT });
console.log(`Range changed! Tx: ${result.txHash}`);

try {
  const details = {
    position: await sdk.getPositionReadable(POSITION_KEY),
    positionDetails: await sdk.getPositionDetailsReadable(POSITION_KEY)
  };
  console.log('Details:');
  printJson(details);
} catch (err) {
  console.log('position read failed:', String(err));
}
