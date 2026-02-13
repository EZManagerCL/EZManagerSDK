import 'dotenv/config';
import { pathToFileURL } from 'node:url';
import { EZManagerSDK } from '../sdk.js';

const POSITION_KEY = '';
const READ_RETRIES = 5;
const READ_RETRY_DELAY_MS = 1200;

export function printJson(value) {
  console.log(JSON.stringify(value, (_, v) => (typeof v === 'bigint' ? v.toString() : v), 2));
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isUnknownBlockError(err) {
  const message = String(err?.message || '');
  const rpcMessage = String(err?.info?.error?.message || '');
  return message.includes('Unknown block') || rpcMessage.includes('Unknown block');
}

export async function runReadPosition({
  sdk,
  key = POSITION_KEY,
  label = 'position',
  blockTag = 'latest',
  retries = READ_RETRIES,
  retryDelayMs = READ_RETRY_DELAY_MS,
  print = true
} = {}) {
  if (!key) throw new Error('POSITION_KEY is required');

  const localSdk = sdk ?? (await EZManagerSDK.fromEnv());
  let lastError = null;

  console.log(`Reading position (${label})...`);

  for (let attempt = 1; attempt <= Math.max(1, Number(retries) || 1); attempt += 1) {
    try {
      const details = {
        positionDetails: await localSdk.getPositionDetailsReadable(key, { blockTag })
      };
      if (print) {
        console.log('Details:');
        printJson(details);
      }
      return details;
    } catch (err) {
      lastError = err;
      if (!isUnknownBlockError(err) || blockTag === 'latest') break;
      console.log(`Block ${blockTag} not available yet, retry ${attempt}/${retries}...`);
      await sleep(retryDelayMs);
    }
  }

  if (blockTag !== 'latest') {
    console.log(`Falling back to latest block for ${label}...`);
    const details = {
      positionDetails: await localSdk.getPositionDetailsReadable(key, { blockTag: 'latest' })
    };
    if (print) {
      console.log('Details:');
      printJson(details);
    }
    return details;
  }

  throw lastError;
}

const isDirectRun = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectRun) {
  await runReadPosition();
}