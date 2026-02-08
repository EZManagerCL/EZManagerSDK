import json
from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk import EZManagerSDK

load_dotenv()

POSITION_KEY = ''
LOWER_PCT = 0.04
UPPER_PCT = 0.03

sdk = EZManagerSDK.from_env()
print('Changing range...')
result = sdk.change_range_by_pct(key=POSITION_KEY, lower_pct=LOWER_PCT, upper_pct=UPPER_PCT)
print(f"Range changed! Tx: {result['tx_hash']}")

try:
    details = {
        'position': sdk.get_position_readable(POSITION_KEY),
        'position_details': sdk.get_position_details_readable(POSITION_KEY),
    }
    print('Details:')
    print(json.dumps(details, indent=2))
except Exception as err:
    print('position read failed:', str(err))
