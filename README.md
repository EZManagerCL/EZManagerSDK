# EZManager SDK

Multi-language EZManager SDK with production-ready JavaScript and Python implementations.

## Repository Layout
- `js/`: JavaScript SDK (Node.js, ESM)
- `python/`: Python SDK

Each language folder is self-contained with:
- its own `README.md`
- its own `.env.example`
- `abi/`
- SDK + utilities
- `examples/` for core user flows

## Chain-Specific Configuration
Address and pool configuration is chain-specific.

- Address files are keyed by chain name (`mainnet`, `base`):
	- `js/addresses.json`
	- `python/addresses.json`
- Supported automatic chain selection:
	- Ethereum Mainnet (`chainId=1`) -> `mainnet`
	- Base (`chainId=8453`) -> `base`
- Any unrecognized chain currently falls back to `base`.

Each language folder also includes chain-scoped allowlisted pools in `ALLOWED_POOLS.md`.

## Choose a Language

Clone the repository:

```bash
git clone https://github.com/EZManagerCL/EZManagerSDK.git
cd EZManagerSDK
```

### JavaScript
```bash
git clone https://github.com/EZManagerCL/EZManagerSDK.git
cd EZManagerSDK/js
```

```bash
# alternative: sparse checkout only js/
git clone --filter=blob:none --sparse https://github.com/EZManagerCL/EZManagerSDK.git
cd EZManagerSDK
git sparse-checkout set js
cd js
```

```bash
cp .env.example .env
# fill RPC_URL and PRIVATE_KEY
npm install
node examples/openPosition.js
```

### Python
```bash
git clone https://github.com/EZManagerCL/EZManagerSDK.git
cd EZManagerSDK/python
```

```bash
# alternative: sparse checkout only python/
git clone --filter=blob:none --sparse https://github.com/EZManagerCL/EZManagerSDK.git
cd EZManagerSDK
git sparse-checkout set python
cd python
```

```bash
cp .env.example .env
# fill RPC_URL and PRIVATE_KEY
pip install -r requirements.txt
python examples/openPosition.py
```

## Core Example Flows (both languages)
- Open position
- Read position
- Add collateral
- Remove collateral
- Change range
- Compound fees
- Collect fees
- Exit position
- End-to-end lifecycle
- List user positions

## Allowlisted Pools
Each language folder includes `ALLOWED_POOLS.md`.
