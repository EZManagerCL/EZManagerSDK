from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from dotenv import load_dotenv

try:
    from .sdk import EZManagerSDK
    from .utils import normalize_bytes32, tick_to_price
except ImportError:
    from sdk import EZManagerSDK
    from utils import normalize_bytes32, tick_to_price


Snapshot = Dict[str, Any]
State = Dict[str, Any]
Action = Dict[str, Any]
DecisionFn = Callable[[Snapshot, State, Dict[str, Any]], Tuple[State, List[Action]]]


def default_state_path(name: str) -> Path:
    return Path(__file__).resolve().parent / 'state' / f'{name}.json'


def usdc_to_raw(value: float | int | str) -> int:
    amount = float(value)
    if amount < 0:
        raise ValueError('USDC amount must be non-negative')
    return int(round(amount * 1_000_000))


def load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {'positions': {}}
    with path.open('r', encoding='utf-8') as fh:
        parsed = json.load(fh)
    if not isinstance(parsed, dict):
        raise ValueError(f'state file must contain a JSON object: {path}')
    parsed.setdefault('positions', {})
    if not isinstance(parsed['positions'], dict):
        raise ValueError(f'state file positions must be an object: {path}')
    return parsed


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    with tmp_path.open('w', encoding='utf-8') as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write('\n')
    tmp_path.replace(path)


def _read_token_decimals(sdk: EZManagerSDK, token: str, cache: Dict[str, int]) -> int:
    token_addr = str(token)
    if token_addr in cache:
        return cache[token_addr]
    contract = sdk.web3.eth.contract(address=token_addr, abi=sdk.abi['ERC20'])
    decimals = int(contract.functions.decimals().call())
    cache[token_addr] = decimals
    return decimals


def read_snapshot(sdk: EZManagerSDK, key: str, decimals_cache: Dict[str, int] | None = None) -> Snapshot:
    cache = decimals_cache if decimals_cache is not None else {}
    normalized_key = normalize_bytes32(key)
    details = sdk.get_position_details_readable(normalized_key)

    token0 = str(details['token0'])
    token1 = str(details['token1'])
    dec0 = _read_token_decimals(sdk, token0, cache)
    dec1 = _read_token_decimals(sdk, token1, cache)

    tick_lower = int(details['tickLower'])
    tick_upper = int(details['tickUpper'])
    current_tick = int(details['currentTick'])

    return {
        'key': normalized_key,
        'observed_at': int(time.time()),
        'token0': token0,
        'token1': token1,
        'token0_decimals': dec0,
        'token1_decimals': dec1,
        'dex': str(details['dex']),
        'tick_spacing': abs(int(details['tickSpacing'])),
        'tick_lower': tick_lower,
        'tick_upper': tick_upper,
        'current_tick': current_tick,
        'lower_price': float(tick_to_price(tick_lower, dec0, dec1)),
        'upper_price': float(tick_to_price(tick_upper, dec0, dec1)),
        'current_price': float(tick_to_price(current_tick, dec0, dec1)),
        'pending_fees_usdc': int(details['pendingFeesUSDC']),
    }


def execute_actions(
    sdk: EZManagerSDK,
    key: str,
    actions: List[Action],
    *,
    execute: bool = False,
    default_slippage: float = 0.005,
) -> List[Dict[str, Any]]:
    normalized_key = normalize_bytes32(key)
    results: List[Dict[str, Any]] = []

    for action in actions or []:
        action_type = str(action.get('type', '')).strip().lower()
        reason = str(action.get('reason', '')).strip()
        slippage = float(action.get('slippage', default_slippage))
        result: Dict[str, Any] = {'type': action_type or 'unknown', 'reason': reason}

        if action_type in ('', 'hold', 'noop'):
            result['status'] = 'skipped'
            results.append(result)
            continue

        if not execute:
            result['status'] = 'planned'
            results.append(result)
            continue

        if action_type == 'set_range':
            lower_price = float(action['lower_price'])
            upper_price = float(action['upper_price'])
            tx = sdk.change_range_by_price(normalized_key, lower_price, upper_price, slippage=slippage)
            result['status'] = 'submitted'
            result['tx_hash'] = tx.get('tx_hash')
            result['lower_price'] = lower_price
            result['upper_price'] = upper_price
        elif action_type == 'compound':
            tx = sdk.compound_fees([normalized_key], slippage=slippage)
            result['status'] = 'submitted'
            result['tx_hash'] = tx.get('tx_hash')
        elif action_type == 'collect':
            tx = sdk.collect_fees_to_usdc([normalized_key], slippage=slippage)
            result['status'] = 'submitted'
            result['tx_hash'] = tx.get('tx_hash')
        elif action_type == 'exit':
            tx = sdk.exit_position([normalized_key], slippage=slippage)
            result['status'] = 'submitted'
            result['tx_hash'] = tx.get('tx_hash')
        else:
            raise ValueError(f'unsupported action type: {action_type}')

        results.append(result)

    return results


def run_strategy(
    *,
    name: str,
    config: Dict[str, Any],
    decide: DecisionFn,
    interval_seconds: int = 30,
    execute: bool = False,
    state_path: str | Path | None = None,
    sdk: EZManagerSDK | None = None,
    once: bool = False,
) -> None:
    if not name or not str(name).strip():
        raise ValueError('strategy name is required')

    position_keys = config.get('position_keys') or []
    if not isinstance(position_keys, list) or not position_keys:
        raise ValueError('config.position_keys must be a non-empty list')

    load_dotenv()
    local_sdk = sdk or EZManagerSDK.from_env()
    resolved_state_path = Path(state_path) if state_path else default_state_path(name)
    state = load_state(resolved_state_path)
    positions_state = state.setdefault('positions', {})
    decimals_cache: Dict[str, int] = {}
    poll_seconds = max(1, int(interval_seconds))
    default_slippage = float(config.get('slippage', 0.005))

    print(f'Starting strategy {name} execute={execute} state={resolved_state_path}')

    while True:
        cycle_started_at = int(time.time())

        for raw_key in position_keys:
            key = normalize_bytes32(raw_key)
            position_state = positions_state.get(key)
            if not isinstance(position_state, dict):
                position_state = {}

            try:
                snapshot = read_snapshot(local_sdk, key, decimals_cache=decimals_cache)
                next_state, actions = decide(snapshot, dict(position_state), config)
                if not isinstance(next_state, dict):
                    raise ValueError('decide(...) must return a state dict as its first value')
                if actions is None:
                    actions = []
                if not isinstance(actions, list):
                    raise ValueError('decide(...) must return a list of actions as its second value')

                results = execute_actions(
                    local_sdk,
                    key,
                    actions,
                    execute=execute,
                    default_slippage=default_slippage,
                )

                if results:
                    next_state['_last_results'] = results
                    next_state['_last_results_at'] = int(time.time())

                positions_state[key] = next_state

                print(
                    json.dumps(
                        {
                            'key': key,
                            'observed_at': snapshot['observed_at'],
                            'current_price': snapshot['current_price'],
                            'lower_price': snapshot['lower_price'],
                            'upper_price': snapshot['upper_price'],
                            'pending_fees_usdc': snapshot['pending_fees_usdc'],
                            'actions': results,
                        },
                        default=str,
                    )
                )
            except KeyboardInterrupt:
                save_state(resolved_state_path, state)
                raise
            except Exception as err:
                position_state['_last_error'] = str(err)
                position_state['_last_error_at'] = int(time.time())
                positions_state[key] = position_state
                print(json.dumps({'key': key, 'error': str(err)}, default=str))

            save_state(resolved_state_path, state)

        if once:
            return

        elapsed = int(time.time()) - cycle_started_at
        sleep_for = max(0, poll_seconds - elapsed)
        time.sleep(sleep_for)
