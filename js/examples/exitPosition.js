import 'dotenv/config';
import { pathToFileURL } from 'node:url';
import { EZManagerSDK } from '../sdk.js';

const POSITION_KEY = '';
const SLIPPAGE_PCT = 0.005; // 0.5%

export async function runExitPosition({ sdk, key = POSITION_KEY, slippage = SLIPPAGE_PCT } = {}) {
  if (!key) throw new Error('POSITION_KEY is required');
  const localSdk = sdk ?? (await EZManagerSDK.fromEnv());

  console.log('Exiting position...');
  const result = await localSdk.exitPosition({ keys: [key], slippage });
  console.log(`Position exited! Tx: ${result.txHash}`);
  return { result };
}

const isDirectRun = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectRun) {
  await runExitPosition();
}
