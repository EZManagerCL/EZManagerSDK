import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

BPS = 10_000
MIN_TICK = -887272
MAX_TICK = 887272
LN_1P0001 = math.log(1.0001)


def load_json(path: Path) -> Any:
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def load_addresses(addresses_path: Path | None = None) -> Dict[str, str]:
    if addresses_path is None:
        addresses_path = Path(__file__).resolve().parent / 'addresses.json'
    return load_json(addresses_path)


def load_abi_map(abi_dir: Path | None = None) -> Dict[str, list]:
    if abi_dir is None:
        abi_dir = Path(__file__).resolve().parent / 'abi'
    files = {
        'ERC20': 'ERC20.json',
        'CL_MANAGER': 'CL_MANAGER.json',
        'CL_CORE': 'CL_CORE.json',
        'UNI_FACTORY': 'UNI_FACTORY.json',
        'SLIP_FACTORY': 'SLIP_FACTORY.json',
        'UNI_POOL': 'UNI_POOL.json',
        'SLIP_POOL': 'SLIP_POOL.json',
        'DEX_ADAPTER': 'DEX_ADAPTER.json',
        'REBALANCE_PLANNER': 'REBALANCE_PLANNER.json',
        'VALUATION': 'VALUATION.json',
    }
    abi: Dict[str, list] = {}
    for key, file_name in files.items():
        parsed = load_json(abi_dir / file_name)
        abi[key] = parsed if isinstance(parsed, list) else parsed.get('abi', [])
    return abi


def normalize_bytes32(value: Any) -> str:
    if isinstance(value, int):
        if value < 0:
            raise ValueError(f'invalid negative bytes32 key: {value}')
        hx = hex(value)[2:]
        if len(hx) > 64:
            raise ValueError(f'invalid bytes32 int too large: {value}')
        return '0x' + hx.rjust(64, '0')

    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        if len(raw) > 32:
            raise ValueError(f'invalid bytes32 bytes length: {len(raw)}')
        return '0x' + raw.hex().rjust(64, '0')

    if isinstance(value, str):
        s = value.strip().lower()
        if s.startswith('0x'):
            s = s[2:]
        if not s:
            raise ValueError(f'invalid empty bytes32 key: {value}')
        if any(ch not in '0123456789abcdef' for ch in s):
            raise ValueError(f'invalid non-hex bytes32 key: {value}')
        if len(s) > 64:
            raise ValueError(f'invalid bytes32 hex too long: {value}')
        return '0x' + s.rjust(64, '0')

    raise ValueError(f'invalid bytes32 key type: {type(value).__name__}')


def sort_tokens(a: str, b: str) -> Tuple[str, str]:
    return (a, b) if a.lower() < b.lower() else (b, a)


def normalize_tick_bounds(lower: float, upper: float, spacing: int) -> Tuple[int, int]:
    lo = min(lower, upper)
    hi = max(lower, upper)
    tick_lower = math.floor(lo / spacing) * spacing
    tick_upper = math.ceil(hi / spacing) * spacing

    min_aligned = math.ceil(MIN_TICK / spacing) * spacing
    max_aligned = math.floor(MAX_TICK / spacing) * spacing

    if tick_lower < min_aligned:
        tick_lower = min_aligned
    if tick_upper > max_aligned:
        tick_upper = max_aligned
    if tick_upper <= tick_lower:
        tick_upper = tick_lower + spacing
    if tick_upper > max_aligned:
        raise ValueError('tick bounds collapse outside valid range')

    return int(tick_lower), int(tick_upper)


def tick_to_price(tick: int, dec0: int = 18, dec1: int = 6) -> float:
    base = math.exp(LN_1P0001 * float(tick))
    scale = 10 ** (dec0 - dec1)
    return base * scale


def price_to_tick(price: float, dec0: int = 18, dec1: int = 6) -> int:
    if price <= 0:
        raise ValueError('price must be > 0')
    scale = 10 ** (dec0 - dec1)
    return int(round(math.log(price / scale) / LN_1P0001))


def to_slippage_bps(slippage: float) -> int:
    if slippage > 1:
        return int(round(slippage))
    return int(round(slippage * 10_000))


def format_units(value: int, decimals: int = 18) -> str:
    value = int(value)
    scale = 10 ** decimals
    whole = value // scale
    frac = value % scale
    frac_str = str(frac).rjust(decimals, '0').rstrip('0')
    return f'{whole}.{frac_str}' if frac_str else str(whole)


def format_usdc(value: int, decimals: int = 6) -> str:
    return f'{format_units(value, decimals)} USDC'
