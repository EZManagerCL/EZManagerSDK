import 'dotenv/config';
import { pathToFileURL } from 'node:url';
import { EZManagerSDK } from '../sdk.js';
import { runReadPosition, printJson } from './readPosition.js';

const POOL_ADDRESS = '0xb2cc224c1c9feE385f8ad6a55b4d94E92359DC59'; // WETH/USDC Aerodrome Example
const OPEN_USDC = '1'; // 1 USDC
const LOWER_PCT = 0.02;
const UPPER_PCT = 0.02;
const SLIPPAGE_PCT = 0.005; // 0.5%

export async function runOpenPosition({
  sdk,
  poolAddress = POOL_ADDRESS,
  usdcAmount = OPEN_USDC,
  lowerPct = LOWER_PCT,
  upperPct = UPPER_PCT,
  slippage = SLIPPAGE_PCT,
  readAfter = true
} = {}) {
  const localSdk = sdk ?? (await EZManagerSDK.fromEnv());

  console.log('Opening position...');
  const result = await localSdk.openPositionByPct({
    poolAddress,
    usdcAmount,
    lowerPct,
    upperPct,
    slippage
  });

  console.log(`Position opened! Tx: ${result.txHash}`);
  if (result.positionKey) console.log(`Key: ${result.positionKey}`);

  const keyToRead = result.positionKey;
  if (!keyToRead) throw new Error('openPositionByPct returned no positionKey; aborting detail lookup.');

  let details = null;
  if (readAfter) {
    details = await runReadPosition({
      sdk: localSdk,
      key: keyToRead,
      label: 'after openPosition',
      blockTag: result?.receipt?.blockNumber ?? 'latest'
    });
  }

  if (!readAfter) {
    printJson({ positionKey: keyToRead });
  }

  return { result, positionKey: keyToRead, details };
}

const isDirectRun = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectRun) {
  await runOpenPosition();
}
