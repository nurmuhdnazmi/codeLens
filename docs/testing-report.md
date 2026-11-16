# CodeLens testing report

Updated: 16 November 2026. Verified application/test revision: `ce81da5c4721433bb5ed57c2a8d8832db8053fbb` (local commit). The logo assets, Streamlit theme and browser-test infrastructure are now tracked. This report is committed separately after verification; application behaviour and the approved catalogue are unchanged.

## Result

**The latest combined run executed 220 tests: 220 passed, 0 failed, 0 skipped, 0 errors.** It completed in 92.64 seconds and returned exit code 0. The two previously failing clean-checkout cases were also rerun separately: 2 passed, 48 deselected in 3.57 seconds. Both viewports now load the application and logo from an archive of committed files.

| Layer | Executed | Passed | Failed | Skipped |
|---|---:|---:|---:|---:|
| Existing core, catalogue, runner and adapter tests | 115 | 115 | 0 | 0 |
| Existing Streamlit AppTest interface tests | 55 | 55 | 0 | 0 |
| Real-browser checks against the working directory | 48 | 48 | 0 | 0 |
| Real-browser startup checks against committed files only | 2 | 2 | 0 | 0 |
| **Total** | **220** | **220** | **0** | **0** |

The [latest full-suite JUnit results](../output/playwright/checkout-fix-full.xml) and [focused checkout results](../output/playwright/checkout-fix-focused.xml) contain the individual outcomes. No application, catalogue, runner, interaction or feedback-adapter code was changed. No failures were marked as expected failures or skipped to make the enabled suite pass.

## Environment and method

- macOS 26.6.2, Apple Silicon; Python 3.11.15; Streamlit 1.67.0; pytest 9.2.0; google-genai 3.3.0.
- Python Playwright 1.65.2 and Chromium 159.0.8154.6, headless. Desktop: 1440 × 1000 CSS pixels. Mobile: 390 × 844, with mobile/touch emulation. These are Chromium viewport checks, not physical-device or Safari tests.
- The existing CLI/browser installation was inspected. The Python Playwright binding and its matching browser were installed for pytest; existing application dependencies were not upgraded. The optional `e2e` dependency now pins Playwright 1.65.2.
- Tests start a real Streamlit subprocess on an available loopback port and execute the actual approved examples through the existing runner. Each case gets a separate browser context. Test servers receive an allowlisted environment without Gemini or other API keys; telemetry is disabled.
- Browser contexts block non-local HTTP requests. The only Live Gemini path exercised in the browser is the missing-key path, which returns before creating a provider client. Existing adapter tests use doubles and guard against real client creation. No live Gemini request was made.
- Actions use accessible roles/names and visible labels, followed by assertions. Explicit application `st-key-*` classes scope sections; semantic `details`/`summary` elements identify expanders. Tests do not use generated CSS classes, forced clicks or direct session-state mutation.
- Streamlit can retain old nodes during a rerender. The helpers wait for unique scoped state captions and, when changing feedback mode, the new mode in rendered metrics before typing. Browser operations use Playwright's waits; the only fixed polling interval is server-health startup polling.
- Every browser case records a trace in memory. A failed case retains a screenshot, DOM accessibility snapshot, trace and browser diagnostics. Passing flows retain selected screenshots and actual downloaded metrics. Trace recording follows the [Playwright tracing API](https://playwright.dev/python/docs/trace-viewer-intro).

Source and environment hashes for the resolved checkout are in the [verification manifest](../output/playwright/checkout-fix-environment.json). The [initial manifest](../output/playwright/environment.json) is retained for the earlier failed revision. Browser cases are in [test_browser.py](../tests/e2e/test_browser.py); server, browser, download and evidence fixtures are in [conftest.py](../tests/e2e/conftest.py).

## Coverage by feature

| Feature | Executed checks and result |
|---|---|
| Three examples and both modes | All six example/mode combinations passed at both viewport sizes: 12 browser cases. |
| List append execution | Actual stdout matched the four reviewed lists. Deliberate repeat runs produced the same result with fresh defaults. |
| Average execution | Actual stdout retained `4.0` before a real `ZeroDivisionError`; traceback, exception status and exit code 1 were displayed. Its expected exception allowed Mock explanation and assessment. |
| Remove duplicates execution | Checked three unique integers, unchanged original input, empty input and repeated identical values. No assertion fixes or promises set iteration order. |
| Prediction submission and locking | Prediction remains text; Run submits it and executes only approved source. No editable prediction remains after execution. Blank/whitespace submissions do not execute. Exactly 2,000 characters can be submitted; an oversized paste cannot produce an over-limit submission. |
| Explicit feedback | No feedback request occurs merely on Run. Mock templates remain labelled predefined and do not claim to grade arbitrary text. Correct template content was checked for each example. |
| Local fix assessment | Correct answers for all three examples, incorrect and Not sure choices, no-choice validation, single submission and locked result were checked. Feedback text does not determine local grading. |
| State resets | Changing example, interaction mode, feedback mode and Start new attempt cleared a completed attempt. Example changes also cleared drafts, validation errors, execution, feedback and a selected but unsubmitted assessment. |
| One run per attempt | Run becomes disabled; guide interactions and repeated metrics downloads preserve result, counters and recorded durations. A deliberate reset permits a fresh run. |
| Session isolation | Separate browser contexts start independently; browser reload starts a fresh attempt. |
| Metrics exports | Actual JSON downloads use the expected filename and 15-field allowlist. Counters, unavailable values, correctness and timing transitions were asserted. Exports remained unchanged across ordinary download reruns. Prediction, source, feedback and traceback fields are excluded. |
| Local Live failure | Missing-key message, no Mock fallback, locked assessment, explicit retry, attempt counts and retained execution were verified without credentials or provider calls. |
| Navigation and layout | Example choices remained visible; mobile sidebar expansion/collapse worked; keyboard Enter opened/closed the guide. Guide and metrics started collapsed. Prediction/stdout headings were side by side on desktop and stacked on mobile, with no whole-document horizontal overflow detected. |
| Runner boundary and uncommon failures | Existing core/AppTest checks passed for rejected IDs/code strings, isolated subprocess settings, empty child environment, timeouts, launch failure, abnormal exits, exception metadata and blocked unrelated feedback. These failure paths were not injected into the real browser server. |
| Committed-checkout startup | Passed on desktop and mobile after the required files were committed. Resolution below. |

All 50 final browser diagnostic records reported zero uncaught JavaScript errors, zero attempted non-local HTTP requests and zero artifact-capture errors. This is browser-side observation, not a general server-network security audit. Coverage here is by feature; line/branch coverage was not measured.

## Resolved failure: committed checkout could not start

**F1 — Resolved in local commit `ce81da5`.**

The affected cases now pass at both viewport sizes:

- `test_committed_checkout_starts_without_local_untracked_files[desktop]`
- `test_committed_checkout_starts_without_local_untracked_files[mobile]`

Before the fix, the fixture's `git archive HEAD` copy lacked `assets/codelens-logo.svg`. The working directory contained it, but it had never been added to Git. `git check-ignore --no-index` confirmed that neither logo nor `.streamlit/config.toml` was excluded by an ignore rule. The clean copy raised `MediaFileStorageError` before rendering Run. The intended theme was likewise absent from Git.

The fix tracks `assets/codelens-logo.svg`, the companion `assets/codelens-mark.svg` and the non-secret `.streamlit/config.toml`. The application/module/asset-reference audit found no other missing repository inputs needed at startup. No ignore exceptions or application-code workaround were needed. Browser tests, the optional pinned Playwright dependency and generated-artifact exclusions were committed with the packaging fix.

Git now lists all three UI files. Secrets, `.venv`, `.env`, generated browser output and the local skill symlinks are not in the commit. Both focused checks and the full suite passed against the committed snapshot, using the existing virtual environment.

Rerun the focused checks from the project root:

```bash
.venv/bin/python -m pytest tests/e2e --run-e2e -q -k committed_checkout
```

This creates a temporary archive of HEAD without removing local files or switching the current checkout. It verifies repository contents using an existing environment; it does not establish fresh dependency-installation success.

Historical failure evidence, captured before the fix: [desktop screenshot](../output/playwright/e2e/20261116T155805Z-27065/test_committed_checkout_starts_without_local_untracked_files_desktop_/failure.png), [desktop trace](../output/playwright/e2e/20261116T155805Z-27065/test_committed_checkout_starts_without_local_untracked_files_desktop_/trace.zip), [mobile screenshot](../output/playwright/e2e/20261116T155805Z-27065/test_committed_checkout_starts_without_local_untracked_files_mobile_/failure.png), [mobile trace](../output/playwright/e2e/20261116T155805Z-27065/test_committed_checkout_starts_without_local_untracked_files_mobile_/trace.zip).

Current evidence: [focused JUnit](../output/playwright/checkout-fix-focused.xml), [full-suite JUnit](../output/playwright/checkout-fix-full.xml), [tracked-file/hash manifest](../output/playwright/checkout-fix-environment.json).

## Visual observations and lower-priority recommendations

Screenshots from the initial desktop/mobile browser pass are retained below. The packaging fix did not change those UI files. The latest browser run again passed the responsive assertions, including stacked comparison headings on mobile.

| Priority | Observation | Recommended follow-up |
|---|---|---|
| Resolved | F1 prevented startup from committed files. | Required assets and theme are now tracked; focused and full-suite verification passed. |
| Low | Pasting 2,500 characters into an empty prediction field leaves it empty on both tested viewports. The 2,000-character submission limit works, but there is no length-specific rejection message at that point. | Consider explicit feedback for an oversized paste. The test records the observed field length and then verifies a valid 2,000-character submission. |
| Low | Mobile mode, feedback and reset controls are behind the collapsed sidebar; long code/traceback lines require horizontal scrolling inside code panels. | Consider pointing to the sidebar toggle in the guide and evaluating a wrap-lines option. These are usability opportunities, not failed functional assertions. |

Examples: [desktop initial interface](../output/playwright/inspection/desktop.png), [mobile initial interface](../output/playwright/inspection/mobile.png), [mobile comparison](../output/playwright/e2e/20261116T155805Z-27065/test_navigation_and_responsive_comparison_mobile_/comparison.png), [oversized-paste field](../output/playwright/e2e/20261116T155805Z-27065/test_prediction_length_limit_and_locked_text_mobile_/oversized-paste.png), [recorded paste behaviour](../output/playwright/e2e/20261116T155805Z-27065/test_prediction_length_limit_and_locked_text_mobile_/length-limit.json).

Only repository packaging was corrected. The lower-priority usability recommendations remain open; no UI behaviour or research-design changes were made.

## Reproduction and artifacts

For a prepared project virtual environment:

```bash
.venv/bin/python -m pip install -e ".[dev,e2e]"
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest -q --run-e2e --junitxml=output/playwright/results.xml
```

These are reproduction instructions; a fresh virtual-environment installation was not performed for this report. Browser tests are opt-in: include `--run-e2e`. An ordinary pytest run omits them. To run only browser checks, use `tests/e2e --run-e2e`. Servers and browser contexts are created and cleaned up by fixtures. Each invocation gets a separate timestamped evidence directory under `output/playwright/e2e/`.

Latest full-suite command (executed after the packaging commit):

```bash
.venv/bin/python -m pytest -q --run-e2e --junitxml=output/playwright/checkout-fix-full.xml
```

Additional checks: `.venv/bin/python -m pip check` reported no broken requirements, with a non-fatal warning that pip's user cache was unwritable. `git diff --check` passed.

Inspect the archived pre-fix failure trace locally:

```bash
.venv/bin/python -m playwright show-trace output/playwright/e2e/20261116T155805Z-27065/test_committed_checkout_starts_without_local_untracked_files_desktop_/trace.zip
```

Artifacts are ignored by Git and must be retained separately if required for submission. Evidence links refer to locally retained output; a fresh clone needs a test rerun or the separately supplied evidence archive. The [testing evidence bundle](../output/playwright/codelens-testing-evidence.zip) contains this report, the final browser evidence, inspection screenshots, environment manifest and JUnit records.

## Execution history

The headline results refer to the latest post-fix combined run. Earlier results below are diagnostics and repeated executions, not additional independent cases.

| Invocation | Executed | Passed | Failed | Skipped |
|---|---:|---:|---:|---:|
| [Existing suite before adding browser tests](../output/playwright/baseline.xml) | 170 | 170 | 0 | 0 |
| [Initial browser locator probe](../output/playwright/e2e-smoke.xml) | 2 | 1 | 1 | 0 |
| [List append flow smoke checks](../output/playwright/e2e-flow-smoke.xml) | 4 | 4 | 0 | 0 |
| [Combined development run 1](../output/playwright/full-run-1.xml) | 220 | 215 | 5 | 0 |
| [Combined development run 2](../output/playwright/full-run-2.xml) | 220 | 217 | 3 | 0 |
| [Length/layout/synchronisation rechecks](../output/playwright/synchronisation-check.xml) | 6 | 6 | 0 | 0 |
| [Combined development run 3](../output/playwright/full-run-3.xml) | 220 | 217 | 3 | 0 |
| [Feedback-mode synchronisation rechecks](../output/playwright/feedback-mode-sync-check.xml) | 2 | 2 | 0 | 0 |
| [Combined development run 4](../output/playwright/full-run-4.xml) | 220 | 217 | 3 | 0 |
| [Pre-fix final combined run](../output/playwright/full-run-final.xml) | 220 | 218 | 2 | 0 |
| [Post-fix focused checkout checks](../output/playwright/checkout-fix-focused.xml) | 2 | 2 | 0 | 0 |
| [Post-fix full suite](../output/playwright/checkout-fix-full.xml) | 220 | 220 | 0 | 0 |

Across these 12 invocations there were 1,506 test executions including repeats: 1,489 passed, 17 failed and 0 skipped. The failures belong to earlier runs; the latest enabled suite has none. Cases excluded by a smoke run's `-k` selector were deselected, not executed or skipped.

Initial harness failures concerned clicking a styled radio's native input, assuming an HTML `maxlength` attribute, measuring a long code element instead of visible comparison headings, transient duplicate render nodes, awaiting a feedback-mode reset and toggling a closing metrics panel. Those test assumptions/synchronisation issues were corrected without changing application code or reducing the behavioural assertions. Their JUnit records remain available. F1 was then resolved by tracking the required files. The latest suite separately verifies the working directory and committed checkout, and both pass.

## Remaining limits and research interpretation

- No successful live Gemini response or real authentication/quota/network/provider failure was exercised. Adapter doubles cover these categories, but do not establish live model compliance or explanation quality.
- Firefox, WebKit/Safari, other operating systems/Python/Streamlit versions, physical phones, load testing, long-lived sessions and a full accessibility audit remain untested. Mobile emulation is not a device-lab result.
- The copied-commit check reused the existing virtual environment. It does not establish fresh-install success or correctness of the full declared dependency-version range.
- The fixed catalogue was not expanded or changed. No browser fault injection was added for runner timeout, launch failure, abnormal exit or unexpected exceptions; existing Python/AppTest coverage supplies that evidence.
- Recorded times include idle time where applicable; no performance SLA was assessed. Functional metrics and fixed-question correctness do not establish developer comprehension, learning gains or a validated assessment measure. Resetting an attempt does not undo prior exposure to output.

These results provide execution and interaction evidence for the reviewed examples in the tested environment. They do not establish correctness for all inputs or actual improvements in developer comprehension.
