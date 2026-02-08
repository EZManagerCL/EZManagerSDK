import 'dotenv/config';
import { EZManagerSDK } from '../sdk.js';

const POSITION_KEY = '';

const sdk = await EZManagerSDK.fromEnv();
console.log('Exiting position...');
const result = await sdk.exitPosition({ keys: [POSITION_KEY] });
console.log(`Position exited! Tx: ${result.txHash}`);
