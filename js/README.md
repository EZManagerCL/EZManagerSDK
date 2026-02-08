# EZManager SDK (JavaScript)

## Setup
1. `cp .env.example .env`
2. Fill `.env` values.
3. `npm install`

## Required Environment
- `RPC_URL`
- `PRIVATE_KEY`

## Core Methods
- `openPosition`
- `addCollateral`
- `removeCollateral`
- `changeRange`
- `changeRangeByPct` (asymmetric: `lowerPct`, `upperPct`)
- `compoundFees`
- `collectFeesToUSDC`
- `exitPosition`

## Examples
Each example defines its own input constants at the top of the file.
- `node examples/openPosition.js`
- `node examples/addCollateral.js`
- `node examples/removeCollateral.js`
- `node examples/changeRange.js`
- `node examples/compoundFees.js`
- `node examples/collectFees.js`
- `node examples/exitPosition.js`

## Debug
- Decode custom error data:
  - `node debug/decodeCustomError.js 0xa86b6512`
- SDK write calls automatically attempt custom error decoding on reverts.

## Allowlisted Pools
See `ALLOWED_POOLS.md`.
