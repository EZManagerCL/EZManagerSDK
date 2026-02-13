import json
from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk import EZManagerSDK

load_dotenv()


def print_json(value):
    print(json.dumps(value, indent=2, default=str))


def run_list_user_positions(sdk: EZManagerSDK | None = None, user: str | None = None):
    local_sdk = sdk or EZManagerSDK.from_env()
    target_user = user or local_sdk.address

    print(f'Listing positions for {target_user}...')
    positions = local_sdk.get_user_position_details_readable(user=target_user)

    details = {
        'user': target_user,
        'count': len(positions),
        'positions': positions,
    }
    print('Details:')
    print_json(details)
    return details


if __name__ == '__main__':
    run_list_user_positions()