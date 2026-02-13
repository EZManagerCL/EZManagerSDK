from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk import EZManagerSDK
from readPosition import run_read_position

load_dotenv()

POSITION_KEY = ''
LOWER_PCT = 0.04
UPPER_PCT = 0.03
SLIPPAGE_PCT = 0.005  # 0.5%


def run_change_range(
    sdk: EZManagerSDK | None = None,
    key: str = POSITION_KEY,
    lower_pct: float = LOWER_PCT,
    upper_pct: float = UPPER_PCT,
    slippage: float = SLIPPAGE_PCT,
    read_after: bool = True,
):
    if not key:
        raise RuntimeError('POSITION_KEY is required')

    local_sdk = sdk or EZManagerSDK.from_env()

    print('Changing range...')
    result = local_sdk.change_range_by_pct(
        key=key,
        lower_pct=lower_pct,
        upper_pct=upper_pct,
        slippage=slippage,
    )
    print(f"Range changed! Tx: {result['tx_hash']}")

    details = None
    if read_after:
        post_block = (result.get('receipt') or {}).get('blockNumber', 'latest')
        details = run_read_position(
            sdk=local_sdk,
            key=key,
            label='after changeRange',
            block_identifier=post_block,
        )

    return {'result': result, 'details': details}


if __name__ == '__main__':
    run_change_range()