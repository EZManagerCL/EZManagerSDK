from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk import EZManagerSDK

load_dotenv()

POSITION_KEY = ''

sdk = EZManagerSDK.from_env()
print('Exiting position...')
result = sdk.exit_position([POSITION_KEY])
print(f"Position exited! Tx: {result['tx_hash']}")
