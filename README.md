# CodeLens

CodeLens is a prototype for students practising how to check Python code against a task’s requirements. Code can look convincing and run without errors while still producing the wrong result. The intended workflow asks users to predict what a suggested solution will do, run it and compare their prediction with the output. Planned feedback and follow-up questions will help them examine the behaviour and decide whether a proposed fix meets the requirements.

Developed for the University of Birmingham’s Intelligent Interactive Systems module, building on my earlier work on developer understanding and verification effort in AI-assisted programming. The examples are deliberately constructed to represent suggestions someone might receive from an AI coding assistant.

## Run locally

Use Python 3.11 or later. The interface uses Streamlit; tests use pytest.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
python -m streamlit run app.py
```

Open the local URL printed by Streamlit. Inspect the complete code, then click
"Run approved example" to see its actual output. Stop the server with Ctrl+C.

## Execution boundary

The runner accepts only a catalogue ID and resolves source internally.
It uses the current interpreter in [isolated mode](https://docs.python.org/3.11/using/cmdline.html#cmdoption-I),
an empty child environment, closed stdin, a temporary directory and no shell.
The [two-second subprocess timeout](https://docs.python.org/3.11/library/subprocess.html#subprocess.run)
kills and waits for the child; process creation itself may take longer.
Elapsed time includes preparation and launch.

An internal wrapper catches `Exception`, preserves its traceback and writes
a marker used to recognise Python exceptions. Uncaught nonzero `SystemExit`,
`KeyboardInterrupt`, signals and failures without that marker are abnormal exits.
Timeout output may be partial; timeout and launch failure have no recorded exit code.
Preparation failures also use the launch-failure status.
Cleanup failures retain the execution evidence and show a separate warning.

This is not an OS security sandbox: the child retains the user's file and network
permissions. The marker is classification support for approved code, not a security
boundary. Results persist within the current Streamlit session, not across a new session.

## Files

- `app.py`: Streamlit page.
- `codelens/catalogue.py`: immutable example and ID lookup.
- `codelens/runner.py`: subprocess execution and structured results.
- `pyproject.toml`: package configuration and dependencies.
- `tests/`: catalogue and rendering checks using Streamlit's [AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).

## Checks

Codex checks: `.venv/bin/python -m pytest -q` passed all 34 tests;
`.venv/bin/python -m pip check` found no broken requirements.
Real subprocess tests cover output, repeat runs, execution boundaries, secret
filtering, Python exceptions, explicit exits and timeout. Controlled doubles cover
launch failure, partial timeout data, signal return codes and UI failure messages.
AppTest checks real execution and persistence across reruns.
Browser inspection is pending. Submission materials will be added later.
