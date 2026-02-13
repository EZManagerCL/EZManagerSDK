import 'dotenv/config';
import { pathToFileURL } from 'node:url';
import { EZManagerSDK } from '../sdk.js';

const POSITION_KEY = '0x1bbdf6a6c66ef4cdcac283c42cb557f24c37b3ce2863becd608ca2b733c0e41b';
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
