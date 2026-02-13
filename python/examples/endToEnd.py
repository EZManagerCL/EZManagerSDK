import time
from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk import EZManagerSDK
from openPosition import run_open_position
from readPosition import run_read_position
from addCollateral import run_add_collateral
from removeCollateral import run_remove_collateral
from collectFees import run_collect_fees
from changeRange import run_change_range
from compoundFees import run_compound_fees
from exitPosition import run_exit_position

load_dotenv()

POOL_ADDRESS = '0xb2cc224c1c9feE385f8ad6a55b4d94E92359DC59'  # WETH/USDC Aerodrome Example
OPEN_USDC = '10'  # $10 USDC initial position size
ADD_COLLATERAL_USDC = '2'
REMOVE_COLLATERAL_USDC = '1'
OPEN_LOWER_PCT = 0.02
OPEN_UPPER_PCT = 0.02
NEW_LOWER_PCT = 0.04
NEW_UPPER_PCT = 0.04

# Time to wait before collecting, then before compounding to allow fees to accrue.
# Set higher for smaller positions to test compound/collect.
WAIT_SECONDS = 120

# 99% slippage, effectively no slippage protection, lets very small amounts not revert.
SLIPPAGE_PCT = 0.99

# Minimum pending fees in USDC to attempt collect or compound
MIN_PENDING_FEES_USDC = '0.001'  # $0.001


def pending_fees_usdc(details) -> int:
    raw = details.get('position_details', {}).get('pendingFeesUSDC', 0)
    return int(raw)


def run_end_to_end(sdk: EZManagerSDK | None = None):
    local_sdk = sdk or EZManagerSDK.from_env()
    min_pending_fees_usdc_raw = local_sdk.parse_usdc(MIN_PENDING_FEES_USDC)

    print('Step 1: Opening +-2% position with $2 USDC...')
    opened = run_open_position(
        sdk=local_sdk,
        pool_address=POOL_ADDRESS,
        usdc_amount=OPEN_USDC,
        lower_pct=OPEN_LOWER_PCT,
        upper_pct=OPEN_UPPER_PCT,
        slippage=SLIPPAGE_PCT,
        read_after=True,
    )
    position_key = opened['position_key']

    print('Step 2: Add $1 collateral...')
    run_add_collateral(
        sdk=local_sdk,
        key=position_key,
        usdc_amount=ADD_COLLATERAL_USDC,
        slippage=SLIPPAGE_PCT,
        read_after=True,
    )

    print('Step 3: Remove $1 collateral...')
    run_remove_collateral(
        sdk=local_sdk,
        key=position_key,
        usdc_amount=REMOVE_COLLATERAL_USDC,
        slippage=SLIPPAGE_PCT,
        read_after=True,
    )

    print(f'Step 4: Wait {WAIT_SECONDS} seconds before collect...')
    time.sleep(WAIT_SECONDS)
    before_collect_details = run_read_position(
        sdk=local_sdk,
        key=position_key,
        label='after wait before collect',
    )

    print('Step 5: Collect fees...')
    if pending_fees_usdc(before_collect_details) < min_pending_fees_usdc_raw:
        print(f'Skipping collect_fees_to_usdc because pendingFeesUSDC is below ${MIN_PENDING_FEES_USDC}.')
    else:
        run_collect_fees(
            sdk=local_sdk,
            key=position_key,
            slippage=SLIPPAGE_PCT,
            read_after=True,
        )

    print('Step 6: Change range to +-4%...')
    run_change_range(
        sdk=local_sdk,
        key=position_key,
        lower_pct=NEW_LOWER_PCT,
        upper_pct=NEW_UPPER_PCT,
        slippage=SLIPPAGE_PCT,
        read_after=True,
    )

    print(f'Step 7: Wait {WAIT_SECONDS} seconds...')
    time.sleep(WAIT_SECONDS)
    before_compound_details = run_read_position(
        sdk=local_sdk,
        key=position_key,
        label='after wait before compound',
    )

    print('Step 8: Compound fees...')
    if pending_fees_usdc(before_compound_details) < min_pending_fees_usdc_raw:
        print(f'Skipping compound_fees because pendingFeesUSDC is below ${MIN_PENDING_FEES_USDC}.')
    else:
        run_compound_fees(
            sdk=local_sdk,
            key=position_key,
            slippage=SLIPPAGE_PCT,
            read_after=True,
        )

    print('Step 9: Exit position...')
    run_exit_position(
        sdk=local_sdk,
        key=position_key,
        slippage=SLIPPAGE_PCT,
    )

    print('End-to-end flow complete.')


if __name__ == '__main__':
    run_end_to_end()