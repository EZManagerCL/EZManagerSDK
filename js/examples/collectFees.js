import 'dotenv/config';
import { EZManagerSDK } from '../sdk.js';

const POSITION_KEY = '';

function printJson(value) {
  console.log(JSON.stringify(value, (_, v) => (typeof v === 'bigint' ? v.toString() : v), 2));
}

const sdk = await EZManagerSDK.fromEnv();
console.log('Collecting fees...');
const result = await sdk.collectFeesToUSDC({ keys: [POSITION_KEY] });
console.log(`Fees collected! Tx: ${result.txHash}`);
const postBlockTag = result?.receipt?.blockNumber ?? 'latest';

try {
  const details = {
    positionDetails: await sdk.getPositionDetailsReadable(POSITION_KEY, { blockTag: postBlockTag })
  };
  console.log('Details:');
  printJson(details);
} catch (err) {
  console.log('position read failed:', String(err));
}
