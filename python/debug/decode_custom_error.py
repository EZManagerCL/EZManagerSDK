from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk import EZManagerSDK


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: python debug/decode_custom_error.py <revertDataHex>')
        return 2

    data = sys.argv[1].strip()

    # Decoder logic uses local ABI set; no RPC/private key required.
    sdk = EZManagerSDK.__new__(EZManagerSDK)
    from utils import load_abi_map
    sdk.abi = load_abi_map()
    sdk.error_selector_map = EZManagerSDK._build_error_selector_map(sdk)

    decoded = EZManagerSDK.decode_custom_error(sdk, data)
    print(decoded)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
