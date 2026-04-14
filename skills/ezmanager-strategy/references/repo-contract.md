# Repo Contract

Use this reference when generating or updating EZManager strategy scripts in this repo.

## File Locations

- Shared runtime: `python/strategy.py`
- User strategies: `python/strategies/*.py`
- Per-strategy JSON state: `python/state/<strategy-name>.json`
- Core SDK: `python/sdk.py`
- Shared utilities: `python/utils.py`

## Required Header Comment

Every generated strategy file should begin with a large plain-English module comment.

Include:
- the strategy's purpose
- the exact trigger conditions
- the exact actions it may execute
- any persisted state it uses
- whether `EXECUTE` defaults to dry-run or live execution

Write this for a human operator, not for the model.

## Runtime Contract

Primary entrypoint:

```python
run_strategy(
    *,
    name: str,
    config: dict,
    decide,
    interval_seconds: int = 30,
    execute: bool = False,
    state_path: str | Path | None = None,
    sdk: EZManagerSDK | None = None,
    once: bool = False,
) -> None
```

Decision function:

```python
def decide(snapshot: dict, state: dict, config: dict) -> tuple[dict, list]:
    ...
```

- First return value: next persisted state for this position
- Second return value: action list

## Normalized Snapshot Keys

`python/strategy.py` currently exposes:

- `key`
- `observed_at`
- `token0`
- `token1`
- `token0_decimals`
- `token1_decimals`
- `dex`
- `tick_spacing`
- `tick_lower`
- `tick_upper`
- `current_tick`
- `lower_price`
- `upper_price`
- `current_price`
- `pending_fees_usdc`

Treat these as facts or straightforward normalizations of on-chain state.
Compute strategy-specific analytics inside the strategy file.

## Supported Actions

Hold / no-op:

```python
{'type': 'hold', 'reason': '...'}
```

Set a new range in price space:

```python
{
    'type': 'set_range',
    'lower_price': 2400.0,
    'upper_price': 2600.0,
    'reason': '...',
}
```

Compound fees:

```python
{'type': 'compound', 'reason': '...'}
```

Collect fees:

```python
{'type': 'collect', 'reason': '...'}
```

Exit position:

```python
{'type': 'exit', 'reason': '...'}
```

Optional per-action slippage override:

```python
{'type': 'compound', 'slippage': 0.01, 'reason': '...'}
```

## Human-Readable Inputs

Keep strategy config human-readable.

Examples:
- `10` means `$10 USDC`
- `0.05` means `5%`
- `600` means `600 seconds`

Use:

```python
from strategy import usdc_to_raw
```

when comparing a human-readable USDC config value against raw snapshot fields such as `pending_fees_usdc`.

## State Guidance

Use state only when needed for cross-poll behavior, such as:
- out-of-range timers
- cooldowns
- last action timestamps
- repeated-trigger suppression

Keep state small and per-position.
Do not introduce a separate storage abstraction for normal strategy requests.
