# CodeLens

CodeLens is a prototype for students practising how to check Python code against a task’s requirements. Code can look convincing and run without errors while still producing the wrong result. The intended workflow asks users to predict what a suggested solution will do, run it and compare their prediction with the output. Mock or optional Gemini feedback and a fixed proposed-fix question complete the current guided flow.

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

Select an example, predict, run, request feedback and assess the replacement.
Answers appear after submission. "Start new attempt" resets; Ctrl+C stops the server.

For Live Gemini, enter the key locally in macOS zsh before launch. Input is hidden
and stays out of shell history:

```zsh
set +x
read -rs 'GEMINI_API_KEY?Gemini API key: '
printf '\n'
export GEMINI_API_KEY
export GEMINI_MODEL='gemini-3.5-flash-lite'
python -m streamlit run app.py
```

Use a supported bare model ID to override the default. Afterwards, run
`unset GEMINI_API_KEY`. Keep keys out of files and screenshots.

## What goes to Google

Live requests send the task, simulation provenance, approved source/calls, locked
prediction, stdout, stderr, status and exception type. Assessment material is excluded.
Do not enter personal or confidential information. Generated explanations may be
wrong; they cannot execute code, alter evidence or grade assessments.

Requests have a 30-second HTTP timeout, 1,024-token output limit and no tools,
automatic retries or continuation. Empty, blocked and incomplete responses keep
assessment locked. Errors are sanitised.

[Google's terms](https://aistudio.google.com/docs/terms) permit product-improvement use
and human review for general unpaid services. UK/EEA/Switzerland follow Paid Services
data-use rules even for unpaid quota: no product-improvement use, but limited abuse
logging. Offering API clients to users there requires Paid Services. Check terms
before hosting for others.

## Execution boundary

Only approved IDs resolve to executable source. Each subprocess uses the current
interpreter in [isolated mode](https://docs.python.org/3.11/using/cmdline.html#cmdoption-I),
an empty environment, closed stdin, a temporary directory, no shell and a
[two-second timeout](https://docs.python.org/3.11/library/subprocess.html#subprocess.run).
This is not an OS sandbox; process creation may exceed that timeout.

Qualified exception metadata makes Average's expected `ZeroDivisionError` eligible.
Printed names cannot do so. Unexpected exceptions, timeouts, launch failures and
abnormal exits block feedback/assessment while retaining evidence. Set iteration
order is unspecified; one matching output cannot establish its ordering guarantee.

## Metrics

JSON exports contain mode, example ID, state, counts, correctness and durations.
Text, code, evidence and credentials are excluded. Data stays in session memory;
reset, selector changes or refresh lose it unless exported.

Durations use a [monotonic clock](https://docs.python.org/3.11/library/time.html#time.monotonic):

- Prediction: attempt creation to valid Run submission, guided mode only.
- Verification: feedback availability to assessment submission.
- Total: creation to assessment submission in guided mode, or program completion in Run-only.

Execution duration comes from the runner; unavailable durations are null. Live
attempt counts include configuration failures, successes count usable responses,
and latency records the latest completed attempt. Mock counts remain separate.
Reruns preserve timings and counts. Times include idle time; modes involve different
activities. These records and question correctness do not establish comprehension.
Reset cannot undo seeing earlier output.

## Files

`app.py` presents the catalogue. `codelens/runner.py` executes approved examples;
`codelens/interaction.py` controls attempts; `codelens/live_feedback.py` handles Gemini.
`tests/` contains core and Streamlit [AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest) checks.

## Checks

Codex checks: `.venv/bin/python -m pytest -q` passed all 170 tests;
`.venv/bin/python -m pip check` found no broken requirements.
Mypy passed for six source files. Provider tests use fake SDK responses; an automatic
guard blocks real Gemini clients. Real subprocess tests remain. Local runtime checks
covered Mock and missing-key behaviour. Browser layout and downloads remain
unchecked. Submission materials will be linked later.

The user reported that the first live List append request returned feedback labelled
`gemini-3.5-flash-lite`. Their review found the output comparison and mutable-default
explanation accurate, but identified an unsupported inference about their understanding
and an insufficiently explicit task comparison. The instructions now separate task,
prediction and observation, require a task-violation check and prohibit knowledge
inferences. The prompt-construction test checks these instructions, not model compliance.
No live retest of the revised prompt or live results for other examples have been reported.

ChatGPT assisted the concept and earlier reference prototype. Codex assisted this
implementation and its automated checks. The live-response review above was performed
and reported by the user.
