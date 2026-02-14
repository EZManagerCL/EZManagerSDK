# EZManager SDK (JavaScript)

## Setup
1. `cp .env.example .env`
2. Fill `.env` values.
3. `npm install`

## Required Environment
- `RPC_URL`
- `PRIVATE_KEY`

## Optional Environment
- `TX_GAS_BUFFER_BPS` (default `2000` = +20%)
- `TX_GAS_BUFFER_MIN` (default `50000` gas)

## Core Methods
- `openPosition`
- `addCollateral`
- `removeCollateral`
- `changeRange`
- `changeRangeByPct` (asymmetric: `lowerPct`, `upperPct`)
- `compoundFees`
- `collectFeesToUSDC`
- `exitPosition`
- `pendingFees`
- `spotAmounts`
- `isPoolAllowed`
- `isPoolDeprecated`
- `listAllowedPools`
- `positionValueUsdc`

## Examples
Each example defines its own input constants at the top of the file.
- `node examples/openPosition.js`
- `node examples/readPosition.js`
- `node examples/addCollateral.js`
- `node examples/removeCollateral.js`
- `node examples/changeRange.js`
- `node examples/compoundFees.js`
- `node examples/collectFees.js`
- `node examples/exitPosition.js`
- `node examples/endToEnd.js`
- `node examples/listUserPositions.js`

## Debug
- Decode custom error data:
  - `node debug/decodeCustomError.js 0xa86b6512`
- SDK write calls attempt custom error decoding on reverts and include extra diagnostics for status=0 failures (including out-of-gas trace hints when available).

## Allowlisted Pools
See `ALLOWED_POOLS.md`.
