# CodeLens

CodeLens is a prototype for students practising how to check Python code against a task’s requirements. Code can look convincing and run without errors while still producing the wrong result. The intended workflow asks users to predict what a suggested solution will do, run it and compare their prediction with the output. A predefined explanation and a fixed proposed-fix question complete the current guided flow.

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

Open Streamlit's local URL. In guided mode, predict all four printed lines, run,
request "Explain my prediction" and assess the replacement. The answer and rationale
appear after submission. "Start new attempt" resets; Ctrl+C stops the server.

## Execution boundary

The runner resolves source from approved IDs. It uses the current interpreter in
[isolated mode](https://docs.python.org/3.11/using/cmdline.html#cmdoption-I), an empty
environment, closed stdin, a temporary directory and no shell. Its
[two-second timeout](https://docs.python.org/3.11/library/subprocess.html#subprocess.run)
stops the child; process creation may take longer. Duration includes preparation.

The wrapper marks caught `Exception` instances. Nonzero `SystemExit`,
`KeyboardInterrupt`, signals and unmarked exits are abnormal. Unexpected exceptions
retain their traceback but cannot receive the normal explanation or assessment.
Runner/process failures block both actions. Timeout output may be partial; timeout
and launch failure have no recorded exit code. Preparation failures use launch-failure
status; cleanup warnings preserve evidence.

This is not an OS security sandbox: file and network permissions remain unchanged.
The exception marker supports classification, not security.

## Metrics

The expandable section and JSON export contain only mode, example ID, state,
counts, correctness and durations. Prediction and answer text, feedback, source,
output, traceback and secrets are excluded. Data stays in session memory without
automatic disk logging; reset, mode change or refresh loses it unless exported.

Durations use a [monotonic clock](https://docs.python.org/3.11/library/time.html#time.monotonic):

- Prediction: attempt creation to valid Run submission, guided mode only.
- Verification: feedback availability to assessment submission.
- Total: creation to assessment submission in guided mode, or program completion in Run-only.

Execution duration comes from the runner. Unavailable durations are null, including
total duration for unfinished or failed attempts. Counts include accepted Run and
feedback requests, even when unavailable, and valid assessment submissions only.
Correctness means matching the catalogue answer; "Not sure" records false.
Times include idle time, and modes involve different activities. Neither these
records nor the single question establish comprehension or learning gains.
Reset cannot undo seeing previous output.

## Files

- `app.py`: Streamlit page.
- `codelens/catalogue.py`: example, mock explanation and proposed-fix question.
- `codelens/runner.py`: subprocess execution and structured results.
- `codelens/interaction.py`: guarded attempt transitions, validation and metrics.
- `tests/`: core checks and Streamlit [AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest) flows.

## Checks

Codex checks: `.venv/bin/python -m pytest -q` passed all 93 tests;
`.venv/bin/python -m pip check` found no broken requirements.
Runner tests retain real execution; controlled doubles cover failure paths.
Controlled clocks test timing without sleeps. AppTest covers all assessment choices,
locking, reset, mode changes, reruns and export payloads. Layout checks now expect
matching prediction/stdout code blocks. Browser layout and download delivery remain
unchecked. Submission materials will be added later.
