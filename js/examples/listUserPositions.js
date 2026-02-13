import 'dotenv/config';
import { pathToFileURL } from 'node:url';
import { EZManagerSDK } from '../sdk.js';

function printJson(value) {
  console.log(JSON.stringify(value, (_, v) => (typeof v === 'bigint' ? v.toString() : v), 2));
}

export async function runListUserPositions({ sdk, user } = {}) {
  const localSdk = sdk ?? (await EZManagerSDK.fromEnv());
  const targetUser = user || localSdk.signer.address;

  console.log(`Listing positions for ${targetUser}...`);
  const positions = await localSdk.getUserPositionDetailsReadable(targetUser);

  const details = {
    user: targetUser,
    count: positions.length,
    positions
  };

  console.log('Details:');
  printJson(details);
  return details;
}

const isDirectRun = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectRun) {
  await runListUserPositions();
}