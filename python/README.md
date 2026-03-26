# EZManager SDK (Python)

## Setup
Requires Python `3.10+`.
1. Copy `.env.example` to `.env`.
2. Fill `.env` values.
3. `pip install -r requirements.txt`

## Required Environment
- `RPC_URL`
- `PRIVATE_KEY`

## Optional Environment
- `TX_GAS_BUFFER_BPS` (default `2000` = +20%)
- `TX_GAS_BUFFER_MIN` (default `50000` gas)

## Chain-Specific Setup
- Addresses are configured in `addresses.json` and must be keyed by chain name:
  - `mainnet`
  - `base`
- SDK chain selection in `EZManagerSDK.from_env()`:
  - `chain_id=1` -> `mainnet`
  - `chain_id=8453` -> `base`
  - any other chain -> `base` fallback

## Core Methods
- `open_position`
- `add_collateral`
- `remove_collateral`
- `change_range`
- `change_range_by_pct` (asymmetric: `lower_pct`, `upper_pct`)
- `compound_fees`
- `collect_fees_to_usdc`
- `exit_position`
- `pending_fees`
- `spot_amounts`
- `is_pool_allowed`
- `is_pool_deprecated`
- `list_allowed_pools`
- `position_value_usdc`

## Examples
Each example defines its own input constants at the top of the file.
- `python examples/openPosition.py`
- `python examples/readPosition.py`
- `python examples/addCollateral.py`
- `python examples/removeCollateral.py`
- `python examples/changeRange.py`
- `python examples/compoundFees.py`
- `python examples/collectFees.py`
- `python examples/exitPosition.py`
- `python examples/endToEnd.py`
- `python examples/listUserPositions.py`

## Debug
- Decode custom error data:
  - `python debug/decode_custom_error.py 0xa86b6512`
- SDK write calls attempt custom error decoding on reverts and include extra diagnostics for status=0 failures (including out-of-gas trace hints when available).

## Allowlisted Pools
See `ALLOWED_POOLS.md` for chain-scoped allowlisted pools (`mainnet` and `base`).
