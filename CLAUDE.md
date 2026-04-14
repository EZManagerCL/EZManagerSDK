# EZManagerSDK

See @README.md for the repository overview, language layout, and setup.

This repository contains the EZManager SDK in:
- `python/`
- `js/`

For EZManager automation and strategy work:
- prefer the Python implementation in `python/`
- use the shared runtime in `python/strategy.py`
- create or update runnable strategy scripts in `python/strategies/`
- keep strategy config human-readable
- keep trading logic in the strategy file, not in the runtime

For detailed strategy-generation guidance, follow:
- @skills/ezmanager-strategy/CLAUDE.md

For agent compatibility with tools that read `AGENT.md`, see:
- @AGENT.md
