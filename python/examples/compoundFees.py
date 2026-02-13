from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk import EZManagerSDK
from readPosition import run_read_position

load_dotenv()

POSITION_KEY = ''
SLIPPAGE_PCT = 0.005  # 0.5%


def run_compound_fees(
    sdk: EZManagerSDK | None = None,
    key: str = POSITION_KEY,
    slippage: float = SLIPPAGE_PCT,
    read_after: bool = True,
):
    if not key:
        raise RuntimeError('POSITION_KEY is required')

    local_sdk = sdk or EZManagerSDK.from_env()

    print('Compounding fees...')
    result = local_sdk.compound_fees([key], slippage=slippage)
    print(f"Fees compounded! Tx: {result['tx_hash']}")

    details = None
    if read_after:
        post_block = (result.get('receipt') or {}).get('blockNumber', 'latest')
        details = run_read_position(
            sdk=local_sdk,
            key=key,
            label='after compoundFees',
            block_identifier=post_block,
        )

    return {'result': result, 'details': details}


if __name__ == '__main__':
    run_compound_fees()