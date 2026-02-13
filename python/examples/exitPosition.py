from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk import EZManagerSDK

load_dotenv()

POSITION_KEY = ''
SLIPPAGE_PCT = 0.005  # 0.5%


def run_exit_position(
    sdk: EZManagerSDK | None = None,
    key: str = POSITION_KEY,
    slippage: float = SLIPPAGE_PCT,
):
    if not key:
        raise RuntimeError('POSITION_KEY is required')

    local_sdk = sdk or EZManagerSDK.from_env()

    print('Exiting position...')
    result = local_sdk.exit_position([key], slippage=slippage)
    print(f"Position exited! Tx: {result['tx_hash']}")
    return {'result': result}


if __name__ == '__main__':
    run_exit_position()