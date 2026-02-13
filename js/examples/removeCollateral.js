import 'dotenv/config';
import { pathToFileURL } from 'node:url';
import { EZManagerSDK } from '../sdk.js';
import { runReadPosition } from './readPosition.js';

const POSITION_KEY = '';
const COLLATERAL_USDC = '1'; // 1 USDC
const SLIPPAGE_PCT = 0.005; // 0.5%

export async function runRemoveCollateral({
  sdk,
  key = POSITION_KEY,
  usdcAmount = COLLATERAL_USDC,
  slippage = SLIPPAGE_PCT,
  readAfter = true
} = {}) {
  if (!key) throw new Error('POSITION_KEY is required');
  const localSdk = sdk ?? (await EZManagerSDK.fromEnv());

  console.log('Removing collateral...');
  const result = await localSdk.removeCollateral({ key, usdcAmount, slippage });
  console.log(`Collateral removed! Tx: ${result.txHash}`);

  let details = null;
  if (readAfter) {
    details = await runReadPosition({
      sdk: localSdk,
      key,
      label: 'after removeCollateral',
      blockTag: result?.receipt?.blockNumber ?? 'latest'
    });
  }

  return { result, details };
}

const isDirectRun = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectRun) {
  await runRemoveCollateral();
}
