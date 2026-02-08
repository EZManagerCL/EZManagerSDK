import json
from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk import EZManagerSDK

load_dotenv()

POOL_ADDRESS = '0xb2cc224c1c9feE385f8ad6a55b4d94E92359DC59' # WETH/USDC Aerodrome Example
OPEN_USDC = '1' # 1 USDC
LOWER_PCT = 0.02
UPPER_PCT = 0.02

sdk = EZManagerSDK.from_env()
print('Opening position...')
result = sdk.open_position_by_pct(
    pool_address=POOL_ADDRESS,
    usdc_amount=OPEN_USDC,
    lower_pct=LOWER_PCT,
    upper_pct=UPPER_PCT,
)
print(f"Position opened! Tx: {result['tx_hash']}")
if result.get('position_key'):
    print(f"Key: {result['position_key']}")

key_to_read = result.get('position_key')
if not key_to_read:
    raise RuntimeError('open_position returned no position_key; aborting detail lookup.')

try:
    position_details = sdk.wait_for_position(
        key_to_read,
        block_identifier='latest',
        attempts=8,
        delay_seconds=0.9,
    )
    details = {
        'position': sdk.get_position_readable(key_to_read, block_identifier='latest'),
        'position_details': position_details,
    }
    print('Details:')
    print(json.dumps(details, indent=2))
except Exception as err:
    print('position read failed:', str(err))
