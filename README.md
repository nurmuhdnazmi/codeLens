# CodeLens

Word count: 324

CodeLens helps students practise checking Python code against task requirements. Its examples simulate AI-generated suggestions: users predict the result, run approved code, inspect evidence, request feedback and assess a proposed fix. Built for the University of Birmingham's Intelligent Interactive Systems module, it follows my Assignment 1 review of code comprehension and verification effort.

## Project status

| Status | Scope |
|---|---|
| Implemented | Three examples; Run-only and guided modes; locked predictions; execution evidence; mock and live Gemini feedback; local fix assessment; JSON metrics. |
| Simulated | Suggested solutions are constructed examples, not captured AI outputs. Mock explanations are predefined. |
| Live checks | Reported for List append and Average. Revised List append feedback still made an unsupported inference about the user's reasoning. |
| Verification gaps | No reported live check for Remove duplicates. Manual rerun-count, assessment-locking and fresh-install results are not recorded here. No user-evaluation results are reported. |

## Technology stack

Python 3.11+ runs the application; Streamlit provides the interface. pytest and mypy support checks. Gemini provides explanations, defaulting to `gemini-3.5-flash-lite`. Execution and grading remain local.

## Run locally

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
python -m streamlit run app.py
```

Windows PowerShell activation:

```powershell
.venv\Scripts\Activate.ps1
```

Mock is the default and needs no key. For Live Gemini, stop Streamlit and enter your own key privately in macOS zsh:

```zsh
set +x
read -rs 'GEMINI_API_KEY?Gemini API key: '
printf '\n'
export GEMINI_API_KEY
export GEMINI_MODEL='gemini-3.5-flash-lite'
python -m streamlit run app.py
```

Windows alternative (PowerShell 7.1+):

```powershell
$env:GEMINI_API_KEY = Read-Host 'Gemini API key' -MaskInput; python -m streamlit run app.py
```

Never commit keys. After stopping Streamlit, clear the variable:

```zsh
unset GEMINI_API_KEY
```

```powershell
Remove-Item Env:GEMINI_API_KEY
```

## Development and AI assistance

ChatGPT supported the concept and earlier reference prototype. Codex assisted code structure, implementation, test-case development and debugging.

I chose the free-tier Gemini integration, configured access and tested List append and Average. Codex revised the instructions, and I retested them; the limitation remained.

Codex previously reported 170 passing tests, no broken dependencies and successful mypy checks. These are historical results, not re-run for this documentation revision.

See the [development record](docs/development-record.md) for stages, reasons, checks and commit references. Gemini integration: [ca59b54](https://github.com/nurmuhdnazmi/codeLens/commit/ca59b5486069c82e2ff3c91d72c521d856de6b5f).

## Limitations and further details

Generated explanations may be wrong. Subprocess execution is not an OS sandbox. Metrics do not establish comprehension, and fix-assessment questions are not a validated measure.

See [live feedback](docs/live-feedback.md), [execution boundary](docs/execution-boundary.md) and [metrics definitions](docs/metrics.md). Do not enter personal or confidential information. Check the provider's current terms before use.
