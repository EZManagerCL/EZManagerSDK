import 'dotenv/config';
import { pathToFileURL } from 'node:url';
import { EZManagerSDK } from '../sdk.js';
import { runReadPosition } from './readPosition.js';

const POSITION_KEY = '';
const SLIPPAGE_PCT = 0.005; // 0.5%

export async function runCompoundFees({
  sdk,
  key = POSITION_KEY,
  slippage = SLIPPAGE_PCT,
  readAfter = true
} = {}) {
  if (!key) throw new Error('POSITION_KEY is required');
  const localSdk = sdk ?? (await EZManagerSDK.fromEnv());

  console.log('Compounding fees...');
  const result = await localSdk.compoundFees({ keys: [key], slippage });
  console.log(`Fees compounded! Tx: ${result.txHash}`);

  let details = null;
  if (readAfter) {
    details = await runReadPosition({
      sdk: localSdk,
      key,
      label: 'after compoundFees',
      blockTag: result?.receipt?.blockNumber ?? 'latest'
    });
  }

  return { result, details };
}

const isDirectRun = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectRun) {
  await runCompoundFees();
}
