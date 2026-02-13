import 'dotenv/config';
import { pathToFileURL } from 'node:url';
import { EZManagerSDK } from '../sdk.js';
import { runReadPosition } from './readPosition.js';

const POSITION_KEY = '';
const LOWER_PCT = 0.04;
const UPPER_PCT = 0.03;
const SLIPPAGE_PCT = 0.005; // 0.5%

export async function runChangeRange({
  sdk,
  key = POSITION_KEY,
  lowerPct = LOWER_PCT,
  upperPct = UPPER_PCT,
  slippage = SLIPPAGE_PCT,
  readAfter = true
} = {}) {
  if (!key) throw new Error('POSITION_KEY is required');
  const localSdk = sdk ?? (await EZManagerSDK.fromEnv());

  console.log('Changing range...');
  const result = await localSdk.changeRangeByPct({ key, lowerPct, upperPct, slippage });
  console.log(`Range changed! Tx: ${result.txHash}`);

  let details = null;
  if (readAfter) {
    details = await runReadPosition({
      sdk: localSdk,
      key,
      label: 'after changeRange',
      blockTag: result?.receipt?.blockNumber ?? 'latest'
    });
  }

  return { result, details };
}

const isDirectRun = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectRun) {
  await runChangeRange();
}
