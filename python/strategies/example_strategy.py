from __future__ import annotations

"""
Example EZManager automation strategy.

This strategy watches the configured position keys on a fixed polling interval.
If the current price stays outside the existing position range for 10 minutes,
it rebalances the position to a new range centered on the current price with
new bounds set to plus or minus 5%.

It also compounds fees whenever pending fees are above $10 USDC.

State usage:
- Stores `out_of_range_since` per position so the 10-minute timer can persist
  across polling cycles and process restarts.

Execution mode:
- `EXECUTE = False` by default, which means the script only plans actions and
  does not submit transactions until the operator switches it to `True`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategy import run_strategy, usdc_to_raw


STRATEGY_NAME = Path(__file__).stem

CONFIG = {
    'position_keys': [
        '',
    ],
    'range_pct': 0.05,
    'rebalance_after_seconds': 600,
    'compound_fee_threshold_usdc': 10,
    'slippage': 0.005,
}

EXECUTE = False
INTERVAL_SECONDS = 30


def choose_range(snapshot: dict, state: dict, config: dict) -> tuple[float, float]:
    range_pct = float(config['range_pct'])
    if not (0 < range_pct < 1):
        raise ValueError('range_pct must be between 0 and 1')

    current_price = float(snapshot['current_price'])
    lower_price = current_price * (1.0 - range_pct)
    upper_price = current_price * (1.0 + range_pct)

    if lower_price <= 0 or upper_price <= lower_price:
        raise ValueError('choose_range produced invalid prices')

    return lower_price, upper_price

def decide(snapshot: dict, state: dict, config: dict) -> tuple[dict, list]:
    next_state = dict(state)
    actions = []

    in_range = snapshot['tick_lower'] <= snapshot['current_tick'] <= snapshot['tick_upper']

    if in_range:
        next_state.pop('out_of_range_since', None)
    else:
        next_state.setdefault('out_of_range_since', snapshot['observed_at'])
        seconds_out = snapshot['observed_at'] - int(next_state['out_of_range_since'])
        if seconds_out >= int(config['rebalance_after_seconds']):
            lower_price, upper_price = choose_range(snapshot, next_state, config)
            actions.append(
                {
                    'type': 'set_range',
                    'lower_price': lower_price,
                    'upper_price': upper_price,
                    'reason': f'price out of range for {seconds_out} seconds',
                }
            )

    if int(snapshot['pending_fees_usdc']) >= usdc_to_raw(config['compound_fee_threshold_usdc']):
        actions.append(
            {
                'type': 'compound',
                'reason': 'pending fees above $10 threshold',
            }
        )

    if not actions:
        actions.append({'type': 'hold', 'reason': 'no rule triggered'})

    return next_state, actions


if __name__ == '__main__':
    run_strategy(
        name=STRATEGY_NAME,
        config=CONFIG,
        decide=decide,
        interval_seconds=INTERVAL_SECONDS,
        execute=EXECUTE,
    )
