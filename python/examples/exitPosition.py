import json
from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk import EZManagerSDK

load_dotenv()

POSITION_KEY = ''

sdk = EZManagerSDK.from_env()
print('Exiting position...')
try:
    details = {
        'position': sdk.get_position_readable(POSITION_KEY),
        'position_details': sdk.get_position_details_readable(POSITION_KEY),
    }
    print('Details:')
    print(json.dumps(details, indent=2))
except Exception as err:
    print(f'Details: position lookup failed ({err})')

result = sdk.exit_position([POSITION_KEY])
print(f"Position exited! Tx: {result['tx_hash']}")
