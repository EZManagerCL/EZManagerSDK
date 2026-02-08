# EZManager SDK (Python)

## Setup
1. Copy `.env.example` to `.env`.
2. Fill `.env` values.
3. `pip install -r requirements.txt`

## Required Environment
- `RPC_URL`
- `PRIVATE_KEY`

## Core Methods
- `open_position`
- `add_collateral`
- `remove_collateral`
- `change_range`
- `change_range_by_pct` (asymmetric: `lower_pct`, `upper_pct`)
- `compound_fees`
- `collect_fees_to_usdc`
- `exit_position`

## Examples
Each example defines its own input constants at the top of the file.
- `python examples/openPosition.py`
- `python examples/addCollateral.py`
- `python examples/removeCollateral.py`
- `python examples/changeRange.py`
- `python examples/compoundFees.py`
- `python examples/collectFees.py`
- `python examples/exitPosition.py`

## Debug
- Decode custom error data:
  - `python debug/decode_custom_error.py 0xa86b6512`
- SDK write calls automatically attempt custom error decoding on reverts.

## Allowlisted Pools
See `ALLOWED_POOLS.md`.
