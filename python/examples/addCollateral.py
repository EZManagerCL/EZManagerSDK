import json
from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk import EZManagerSDK

load_dotenv()

POSITION_KEY = ''
COLLATERAL_USDC = '1'  # 1 USDC

sdk = EZManagerSDK.from_env()
print('Adding collateral...')
result = sdk.add_collateral(key=POSITION_KEY, usdc_amount=COLLATERAL_USDC)
print(f"Collateral added! Tx: {result['tx_hash']}")

try:
    details = {
        'position': sdk.get_position_readable(POSITION_KEY),
        'position_details': sdk.get_position_details_readable(POSITION_KEY),
    }
    print('Details:')
    print(json.dumps(details, indent=2))
except Exception as err:
    print('position read failed:', str(err))
