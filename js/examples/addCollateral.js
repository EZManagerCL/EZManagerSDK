import 'dotenv/config';
import { EZManagerSDK } from '../sdk.js';

const POSITION_KEY = '';
const COLLATERAL_USDC = '1'; // 1 USDC


function printJson(value) {
  console.log(JSON.stringify(value, (_, v) => (typeof v === 'bigint' ? v.toString() : v), 2));
}

const sdk = await EZManagerSDK.fromEnv();
console.log('Adding collateral...');
const result = await sdk.addCollateral({ key: POSITION_KEY, usdcAmount: COLLATERAL_USDC });
console.log(`Collateral added! Tx: ${result.txHash}`);
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
