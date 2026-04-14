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
  - `arbitrum`
- SDK chain selection in `EZManagerSDK.from_env()`:
  - `chain_id=1` -> `mainnet`
  - `chain_id=8453` -> `base`
  - `chain_id=42161` -> `arbitrum`
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
See `ALLOWED_POOLS.md` for chain-scoped allowlisted pools (`mainnet`, `base`, and `arbitrum`).

## Strategy Harness
- Shared runtime: `python/strategy.py`
- User strategies: `python/strategies/`
- Per-strategy state JSON: `python/state/<strategy-name>.json`
- Repo-local Codex skill: `skills/ezmanager-strategy`
- Claude Code project instructions: `CLAUDE.md`

The strategy harness is intentionally small:
- `run_strategy(...)` polls managed positions, loads/saves JSON state, reads normalized snapshots, and executes returned actions.
- User strategy files own the policy logic by defining `decide(snapshot, state, config)` and, when needed, helpers like `choose_range(...)`.
- Strategy config is human-readable. For example, use `10` for `$10 USDC`; the runtime exposes `usdc_to_raw(...)` when a strategy needs raw on-chain units.
- Range decisions should be made in price space by returning `lower_price` and `upper_price`.
- New strategy files should start with a large plain-English header comment describing behavior, triggers, state, and execute mode.

Example:
- `python strategies/example_strategy.py`
- Set `position_keys`
- Leave `EXECUTE = False` for dry-run planning
- Switch `EXECUTE = True` to submit transactions

Quick non-coder workflow:
1. Fill `python/.env` with `RPC_URL` and `PRIVATE_KEY`.
2. Ask Claude Code or Codex to create a strategy in plain language.
3. Paste your position key into the generated file's `CONFIG["position_keys"]`.
4. Run the script with `EXECUTE = False`.
5. Switch to `EXECUTE = True` only after the planned actions look correct.

Example agent prompt:

```text
Use the EZManager strategy skill in this repo to create a strategy that rebalances to +-5% if price is out of range for 10 minutes and compounds fees above $10.
```

The repo-local skill is intended to turn plain-language strategy requests into runnable files in `python/strategies/` using the shared runtime.

Relevant AI files:
- `skills/ezmanager-strategy/SKILL.md`
- `skills/ezmanager-strategy/CLAUDE.md`
- `skills/ezmanager-strategy/references/repo-contract.md`
- `CLAUDE.md`
- `AGENT.md`
