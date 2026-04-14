# EZManager Strategy Instructions

Use these instructions when creating or updating EZManager automation strategies in this repo.

@skills/ezmanager-strategy/references/repo-contract.md

## Scope

Create or update one runnable Python strategy script under `python/strategies/`.

Target output:
- one strategy file
- uses `python/strategy.py`
- keeps config human-readable
- keeps trading logic in the strategy file

Do not create extra framework layers, registries, plugin systems, or packages unless the user explicitly asks.

## Required Rules

- Use Python, not JavaScript or TypeScript.
- Prefer editing or creating a single strategy file in `python/strategies/`.
- Only change `python/strategy.py` if the change is truly generic across strategies.
- Keep USDC config values human-readable.
  Use `10` for `$10 USDC`, not raw `10000000`.
- Use price-based range actions with `lower_price` and `upper_price`.
- Keep state minimal and per-position.
- Default new strategies to `EXECUTE = False` unless the user explicitly asks for live execution by default.

## Required Header Comment

Start every generated strategy file with a large plain-English module comment that explains:
- what the strategy does
- exact trigger conditions
- exact actions it may execute
- any persisted state it uses
- whether it defaults to dry-run or live execution

Write the comment for a human operator.

## Strategy Shape

Use this structure unless the user explicitly wants something else:

```python
"""
Plain-English summary of strategy behavior.
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

## Plain-Language Conversion

Translate the user request directly into a small strategy:
- timers like "10 minutes" become config seconds
- thresholds like "$10 fees" become human-readable config values
- only keep state required for the described behavior

Examples:
- "out of range for 10 minutes" -> persist `out_of_range_since`
- "compound above $10" -> compare raw snapshot fees against `usdc_to_raw(config['compound_fee_threshold_usdc'])`

## Validation

After edits, run:

```bash
python -m py_compile python/strategy.py python/strategies/<strategy_file>.py
```

If live execution was not tested, state that clearly.
