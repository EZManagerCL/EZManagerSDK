import json
import time
from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk import EZManagerSDK

load_dotenv()

POSITION_KEY = ''
READ_RETRIES = 5
READ_RETRY_DELAY_SECONDS = 1.2


def print_json(value):
    print(json.dumps(value, indent=2, default=str))


def _is_unknown_block_error(err: Exception) -> bool:
    msg = str(err)
    return 'Unknown block' in msg


def run_read_position(
    sdk: EZManagerSDK | None = None,
    key: str = POSITION_KEY,
    label: str = 'position',
    block_identifier='latest',
    attempts: int = READ_RETRIES,
    delay_seconds: float = READ_RETRY_DELAY_SECONDS,
    print_output: bool = True,
):
    if not key:
        raise RuntimeError('POSITION_KEY is required')

    local_sdk = sdk or EZManagerSDK.from_env()
    last_error: Exception | None = None

    print(f'Reading position ({label})...')

    for attempt in range(1, max(1, int(attempts)) + 1):
        try:
            details = {
                'position_details': local_sdk.get_position_details_readable(
                    key,
                    block_identifier=block_identifier,
                )
            }
            if print_output:
                print('Details:')
                print_json(details)
            return details
        except Exception as err:
            last_error = err
            if not _is_unknown_block_error(err) or block_identifier == 'latest':
                break
            print(f'Block {block_identifier} not available yet, retry {attempt}/{attempts}...')
            time.sleep(max(0.0, float(delay_seconds)))

    if block_identifier != 'latest':
        print(f'Falling back to latest block for {label}...')
        details = {
            'position_details': local_sdk.get_position_details_readable(
                key,
                block_identifier='latest',
            )
        }
        if print_output:
            print('Details:')
            print_json(details)
        return details

    raise last_error or RuntimeError('Failed to read position')


if __name__ == '__main__':
    run_read_position()