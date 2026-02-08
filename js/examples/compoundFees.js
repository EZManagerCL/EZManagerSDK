import 'dotenv/config';
import { EZManagerSDK } from '../sdk.js';

const POSITION_KEY = '';

function printJson(value) {
  console.log(JSON.stringify(value, (_, v) => (typeof v === 'bigint' ? v.toString() : v), 2));
}

const sdk = await EZManagerSDK.fromEnv();
console.log('Compounding fees...');
const result = await sdk.compoundFees({ keys: [POSITION_KEY] });
console.log(`Fees compounded! Tx: ${result.txHash}`);

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
