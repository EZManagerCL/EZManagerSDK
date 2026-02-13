import 'dotenv/config';
import { pathToFileURL } from 'node:url';
import { EZManagerSDK } from '../sdk.js';
import { runReadPosition } from './readPosition.js';

const POSITION_KEY = '';
const SLIPPAGE_PCT = 0.005; // 0.5%

export async function runCollectFees({
  sdk,
  key = POSITION_KEY,
  slippage = SLIPPAGE_PCT,
  readAfter = true
} = {}) {
  if (!key) throw new Error('POSITION_KEY is required');
  const localSdk = sdk ?? (await EZManagerSDK.fromEnv());

  console.log('Collecting fees...');
  const result = await localSdk.collectFeesToUSDC({ keys: [key], slippage });
  console.log(`Fees collected! Tx: ${result.txHash}`);

  let details = null;
  if (readAfter) {
    details = await runReadPosition({
      sdk: localSdk,
      key,
      label: 'after collectFees',
      blockTag: result?.receipt?.blockNumber ?? 'latest'
    });
  }

  return { result, details };
}

const isDirectRun = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectRun) {
  await runCollectFees();
}
