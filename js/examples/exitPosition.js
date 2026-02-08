import 'dotenv/config';
import { EZManagerSDK } from '../sdk.js';

const POSITION_KEY = '';

function printJson(value) {
  console.log(JSON.stringify(value, (_, v) => (typeof v === 'bigint' ? v.toString() : v), 2));
}

const sdk = await EZManagerSDK.fromEnv();
console.log('Exiting position...');
try {
  const details = {
    position: await sdk.getPositionReadable(POSITION_KEY),
    positionDetails: await sdk.getPositionDetailsReadable(POSITION_KEY)
  };
  console.log('Details:');
  printJson(details);
} catch (err) {
  console.log(`Details: position lookup failed (${String(err)})`);
}

const result = await sdk.exitPosition({ keys: [POSITION_KEY] });
console.log(`Position exited! Tx: ${result.txHash}`);
