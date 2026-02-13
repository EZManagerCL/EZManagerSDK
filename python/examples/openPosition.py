from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk import EZManagerSDK
from readPosition import run_read_position

load_dotenv()

POOL_ADDRESS = '0xb2cc224c1c9feE385f8ad6a55b4d94E92359DC59'  # WETH/USDC Aerodrome Example
OPEN_USDC = '1'  # 1 USDC
LOWER_PCT = 0.02
UPPER_PCT = 0.02
SLIPPAGE_PCT = 0.005  # 0.5%


def run_open_position(
    sdk: EZManagerSDK | None = None,
    pool_address: str = POOL_ADDRESS,
    usdc_amount: str = OPEN_USDC,
    lower_pct: float = LOWER_PCT,
    upper_pct: float = UPPER_PCT,
    slippage: float = SLIPPAGE_PCT,
    read_after: bool = True,
):
    local_sdk = sdk or EZManagerSDK.from_env()

    print('Opening position...')
    result = local_sdk.open_position_by_pct(
        pool_address=pool_address,
        usdc_amount=usdc_amount,
        lower_pct=lower_pct,
        upper_pct=upper_pct,
        slippage=slippage,
    )
    print(f"Position opened! Tx: {result['tx_hash']}")

    position_key = result.get('position_key')
    if position_key:
        print(f'Key: {position_key}')
    else:
        raise RuntimeError('open_position returned no position_key; aborting detail lookup.')

    details = None
    if read_after:
        post_block = (result.get('receipt') or {}).get('blockNumber', 'latest')
        details = run_read_position(
            sdk=local_sdk,
            key=position_key,
            label='after openPosition',
            block_identifier=post_block,
        )

    return {'result': result, 'position_key': position_key, 'details': details}


if __name__ == '__main__':
    run_open_position()