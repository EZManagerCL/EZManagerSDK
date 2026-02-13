from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk import EZManagerSDK
from readPosition import run_read_position

load_dotenv()

POSITION_KEY = ''
COLLATERAL_USDC = '1'  # 1 USDC
SLIPPAGE_PCT = 0.005  # 0.5%


def run_add_collateral(
    sdk: EZManagerSDK | None = None,
    key: str = POSITION_KEY,
    usdc_amount: str = COLLATERAL_USDC,
    slippage: float = SLIPPAGE_PCT,
    read_after: bool = True,
):
    if not key:
        raise RuntimeError('POSITION_KEY is required')

    local_sdk = sdk or EZManagerSDK.from_env()

    print('Adding collateral...')
    result = local_sdk.add_collateral(key=key, usdc_amount=usdc_amount, slippage=slippage)
    print(f"Collateral added! Tx: {result['tx_hash']}")

    details = None
    if read_after:
        post_block = (result.get('receipt') or {}).get('blockNumber', 'latest')
        details = run_read_position(
            sdk=local_sdk,
            key=key,
            label='after addCollateral',
            block_identifier=post_block,
        )

    return {'result': result, 'details': details}


if __name__ == '__main__':
    run_add_collateral()