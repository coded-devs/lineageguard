# LineageGuard

Takes a simulated schema change, queries local OpenMetadata to walk downstream lineage, and classifies impact severity.

Under active development — see GEMINI.md for architecture.

## Setup
- Install Python 3.11
- Create a virtual environment: `python -m venv .venv`
- Install the package: `pip install -e .`
