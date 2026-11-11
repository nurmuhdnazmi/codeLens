# CodeLens

CodeLens is a prototype for inspecting simulated AI-generated Python suggestions,
built for the University of Birmingham Intelligent Interactive Systems assignment.

## Status

Stage 1 displays one example with its task and source code.
Code execution and the guided verification flow will follow in later stages.

## Run locally

Use Python 3.11 or later. The interface uses Streamlit; tests use pytest.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
python -m streamlit run app.py
```

Open the local URL printed by Streamlit. Check that the "List append" example
shows its task and code. Stop the server with Ctrl+C.

## Files

- `app.py`: Streamlit page.
- `codelens/catalogue.py`: immutable example and ID lookup.
- `pyproject.toml`: package configuration and dependencies.
- `tests/`: catalogue and rendering checks using Streamlit's [AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).

## Checks

Recorded automated checks: `.venv/bin/python -m pytest -q` passed all seven tests;
`.venv/bin/python -m pip check` found no broken requirements.
Browser inspection is pending. Submission materials will be added later.
