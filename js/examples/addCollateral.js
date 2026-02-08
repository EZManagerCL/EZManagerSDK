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
