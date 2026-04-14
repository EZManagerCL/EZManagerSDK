---
name: ezmanager-strategy
description: Generate or update EZManager Python strategy scripts from plain-language automation rules. Use when working in the EZManagerSDK repo to turn a user request like "rebalance to +-5% after 10 minutes out of range" or "compound above $10 fees" into a single runnable script under `python/strategies/` that uses `python/strategy.py`, keeps inputs human-readable, persists per-strategy JSON state only when needed, and avoids introducing extra framework layers.
---

# EZManager Strategy

Use this skill to create or modify one self-contained Python strategy script for this repo.

Target output:
- one file in `python/strategies/`
- imports `run_strategy` from `python/strategy.py`
- keeps user-facing config human-readable
- implements policy logic in the strategy file, not in the runtime

Do not build extra runtime layers, plugin systems, registries, or packages unless the user explicitly asks.

## Workflow

1. Inspect `python/strategy.py` and the current strategy files in `python/strategies/`.
2. If needed, read `references/repo-contract.md` for the repo-specific contract.
3. Create or update exactly one strategy script unless the user explicitly asks for more.
4. Keep config values human-readable.
5. Keep the strategy logic easy to scan: `CONFIG`, optional helpers like `choose_range(...)`, then `decide(...)`, then `run_strategy(...)`.
6. Run `python -m py_compile` on the changed Python files.

## Required Constraints

- Use Python, not JavaScript or TypeScript.
- Put reusable mechanics in `python/strategy.py` only if they are truly generic across strategies.
- Put trading logic in the user strategy file.
- Prefer one strategy file per request.
- Start every generated strategy file with a large plain-English module comment that explains exactly what the strategy does, when it acts, what it will execute, what state it keeps, and whether it defaults to dry-run or live execution.
- Keep USDC config values human-readable.
  Use `10` for `$10 USDC`, not raw `10000000`.
- Use price-space decisions for ranges.
  Return actions like `set_range` with `lower_price` and `upper_price`.
- Use JSON state only when the strategy actually needs memory across polls or restarts.
- Default new strategies to `EXECUTE = False` unless the user explicitly wants live execution by default.

## Strategy File Shape

Use this structure unless the user explicitly wants something else:

```python
"""
Plain-English strategy summary.
Describe the trigger conditions, actions, state usage, and execute mode.
"""

STRATEGY_NAME = Path(__file__).stem

CONFIG = {
    ...
}

EXECUTE = False
INTERVAL_SECONDS = 30

def choose_range(snapshot: dict, state: dict, config: dict) -> tuple[float, float]:
    ...

def decide(snapshot: dict, state: dict, config: dict) -> tuple[dict, list]:
    ...

if __name__ == '__main__':
    run_strategy(...)
```

Omit `choose_range(...)` if the strategy does not need it.

## Snapshot And Action Contract

Read `references/repo-contract.md` when you need the exact normalized snapshot keys or supported action types.

Do not invent new snapshot fields in `python/strategy.py` unless they are straightforward normalizations of observable on-chain data.
Do not push strategy-specific derived analytics into the runtime.

## Plain-Language Conversion Rule

When the user describes a strategy in plain language:
- translate timers like "10 minutes" into config seconds
- translate fee thresholds like "$10" into human-readable config values
- convert the description into a small `decide(...)` function
- add only the minimum state needed for the stated behavior

Example:
- "rebalance if out of range for 10 minutes"
  Store `out_of_range_since` in state.
- "compound above $10 fees"
  Compare `snapshot['pending_fees_usdc']` against `usdc_to_raw(config['compound_fee_threshold_usdc'])`.

## Editing Guidance

- Update `python/README.md` only if the workflow meaningfully changes.
- Avoid touching SDK internals for a strategy-only request.
- Keep comments sparse and useful.
- Use existing helpers from `python/utils.py` and `python/strategy.py` instead of duplicating conversions.

## Validation

Always run `python -m py_compile` on the changed strategy/runtime files.
If execution was not tested live, state that clearly.
