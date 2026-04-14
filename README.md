# EZManager SDK

Multi-language EZManager SDK with production-ready JavaScript and Python implementations, plus a repo-native Python strategy harness for AI-generated automation scripts.

## Repository Layout
- `python/`: Python SDK, strategy runtime, and example strategies
- `js/`: JavaScript SDK (Node.js, ESM)
- `skills/ezmanager-strategy/`: repo-local strategy skill for Codex and Claude-style agents
- `CLAUDE.md`: Claude Code project instructions
- `AGENT.md`: Codex/Copilot-style project instructions

Each language folder is self-contained with:
- its own `README.md`
- its own `.env.example`
- `abi/`
- SDK + utilities
- `examples/` for core user flows

## AI-Native Workflow

This repo is set up so an AI agent can generate runnable EZManager automation strategies directly into the repo.

Main strategy files:
- `python/strategy.py`: shared runtime for polling, normalized snapshots, JSON state, and action execution
- `python/strategies/example_strategy.py`: simple example strategy
- `python/state/`: per-strategy JSON state written automatically when needed

Agent entrypoints:
- `skills/ezmanager-strategy/SKILL.md`: Codex-style skill instructions
- `skills/ezmanager-strategy/CLAUDE.md`: Claude-compatible strategy instructions
- `skills/ezmanager-strategy/references/repo-contract.md`: exact strategy/runtime contract

Expected agent output:
- one Python strategy file under `python/strategies/`
- human-readable config values
- a large plain-English comment at the top describing exactly what the strategy does
- `EXECUTE = False` by default unless live execution is explicitly requested

Example plain-language request:

```text
Create a strategy that rebalances to +-5% if price stays out of range for 10 minutes and compounds fees above $10.
```

## Getting Started

If you do not know how to code, the intended path is:

1. Clone this repo.
2. Set up the Python environment.
3. Open the repo in Claude Code or Codex.
4. Ask the agent to generate a strategy for you.
5. Paste in your position key.
6. Run the strategy in dry-run mode first.

Minimal setup:

```bash
git clone https://github.com/EZManagerCL/EZManagerSDK.git
cd EZManagerSDK/python
cp .env.example .env
pip install -r requirements.txt
```

Then fill `python/.env` with:
- `RPC_URL`
- `PRIVATE_KEY`

Then ask your agent for a strategy.

Example prompts:

```text
Use the EZManager strategy skill in this repo to create a strategy that rebalances to +-5% if price is out of range for 10 minutes and compounds fees above $10.
```

```text
Use the EZManager strategy skill in this repo to create a strategy for my position that rebalances to +-3% after 20 minutes out of range and collects fees above $15 instead of compounding.
```

```text
Use the EZManager strategy skill in this repo to create a very simple strategy that only compounds when fees are above $25 and otherwise does nothing.
```

After the strategy file is created:
- open the generated file in `python/strategies/`
- paste your position key into `CONFIG["position_keys"]`
- keep `EXECUTE = False`
- run it once or continuously from `python/`

```bash
python strategies/example_strategy.py
```

When the planned actions look correct, change `EXECUTE = True` in the generated strategy file to allow live transactions.

## Choose a Language

Clone the repository:

```bash
git clone https://github.com/EZManagerCL/EZManagerSDK.git
cd EZManagerSDK
```

### Python

Use Python if you want SDK usage plus the built-in automation harness.

```bash
cd python
cp .env.example .env
# fill RPC_URL and PRIVATE_KEY
pip install -r requirements.txt
python examples/openPosition.py
```

Read more:
- `python/README.md`

### JavaScript

Use JavaScript if you only need the SDK.

```bash
cd js
cp .env.example .env
# fill RPC_URL and PRIVATE_KEY
npm install
node examples/openPosition.js
```

Read more:
- `js/README.md`

## Python Strategy Harness

The Python side includes a small shared runtime for automated position management:

- reads normalized position snapshots from on-chain state
- lets strategy files define their own rules in `decide(...)`
- keeps user-facing config human-readable
- writes per-strategy JSON state only when needed
- executes actions like `set_range`, `compound`, `collect`, and `exit`

To run the example strategy:

```bash
cd python
python strategies/example_strategy.py
```

Before running:
- set `position_keys` in `python/strategies/example_strategy.py`
- keep `EXECUTE = False` for dry-run planning
- switch `EXECUTE = True` only when ready to send live transactions

## Chain-Specific Configuration

Address and pool configuration is chain-specific.

- Address files are keyed by chain name (`mainnet`, `base`, `arbitrum`):
  - `js/addresses.json`
  - `python/addresses.json`
- Supported automatic chain selection:
  - Ethereum Mainnet (`chainId=1`) -> `mainnet`
  - Base (`chainId=8453`) -> `base`
  - Arbitrum (`chainId=42161`) -> `arbitrum`
- Any unrecognized chain currently falls back to `base`.

Each language folder also includes chain-scoped allowlisted pools in `ALLOWED_POOLS.md`.

## Core Example Flows

Available in both SDKs:
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
