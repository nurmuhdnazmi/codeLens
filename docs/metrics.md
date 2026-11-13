# Metrics definitions

`Attempt.metrics()` in `codelens/interaction.py` exports an explicit allowlist for the current attempt. The interface shows it and offers `codelens-attempt.json` for download. It does not aggregate attempts or store them in a database.

## Exported fields

| Field | Meaning |
|---|---|
| `mode` | `Run-only` or `Predict–Explain–Verify`. |
| `example_id` | Selected approved catalogue ID. |
| `state` | Current attempt state: `ready`, `running`, `completed`, `failed`, `feedback_ready`, `feedback_unavailable`, `feedback_requesting`, `feedback_failed` or `verified`. |
| `execution_count` | Accepted Run actions: zero or one. Includes a run ending in launch failure; invalid prediction submission does not increment it. |
| `mock_feedback_request_count` | Zero or one accepted Mock explanation action. Also becomes one when the predefined explanation is unavailable for unexpected evidence. Live actions do not increment it. |
| `verification_submission_count` | Zero or one valid assessment submission. Submitting without a valid choice does not increment it. |
| `verification_correct` | `null` until valid submission, then whether the choice matches the catalogue answer. `Not sure` records `false`. |
| `prediction_duration_seconds` | Guided attempt creation to valid Run submission. `null` before that action and throughout Run-only mode. |
| `execution_duration_seconds` | Runner's recorded elapsed time, or `null` before a result. Includes failed execution results. |
| `verification_duration_seconds` | Feedback availability to valid assessment submission. `null` until submission. |
| `total_duration_seconds` | Attempt creation to valid assessment submission in guided mode, or to completed program evidence in Run-only mode. `null` for unfinished guided attempts and failed Run-only executions. |
| `feedback_mode` | `Mock` or `Live Gemini`. Run-only records `Mock` but does not request feedback. |
| `live_feedback_request_attempts` | Number of accepted explicit Live explanation/retry actions. Includes missing-key and configuration failures even when no HTTP request occurs. Ineligible execution evidence does not increment it. |
| `live_feedback_success_count` | Number of usable Live responses accepted into the attempt: zero or one. This is not an accuracy score. |
| `live_feedback_latency_seconds` | Duration of the latest completed Live attempt, whether successful or failed. `null` before any completion and in Mock mode. |

## Timing and counters

Attempt timings use a monotonic clock. Prediction time starts when the attempt is created, rather than when typing begins. A valid guided Run locks that duration and the prediction. Rejected blank or overlength predictions leave the duration unavailable; subsequent valid submission still measures from creation.

Execution duration uses the runner's performance clock: after catalogue lookup, before preparing the temporary directory, through process execution and output capture. Normal directory cleanup is excluded. See the [execution boundary](execution-boundary.md).

Verification starts when predefined feedback becomes available or a usable Live response is accepted. It stops on the first valid assessment submission, including an incorrect or `Not sure` choice. An invalid selection does not stop it. Guided total time covers the entire attempt through that submission, including execution, waiting before feedback, provider requests and retries. Run-only total time stops when a `success` or `python_exception` result is accepted; timeouts, launch failures and abnormal exits leave it `null`.

Live latency begins when an eligible explicit request is accepted and ends when its outcome is recorded. It includes local validation and failure handling, so a missing-key result still has a latency and an attempt count. During a retry, the last completed latency remains until the new outcome replaces it. This is an application request duration, not a provider-only processing measurement or an HTTP request count.

A successful Live response means usable text accepted after the adapter's blocking, finish-reason, content and length checks. It does not mean a correct explanation or compliance with the instructions. Provider failures and rejected responses do not increment the success count. See [live feedback](live-feedback.md) for those checks.

Ordinary Streamlit reruns do not execute another subprocess, repeat feedback requests or increment counters. Recorded durations remain fixed after their corresponding events; the export does not show a continuously increasing timer. Failed Live attempts can add request attempts through explicit retries. Execution and assessment are each limited to one per attempt.

## Retention and interpretation

Attempt data stays in Streamlit session memory. **Start new attempt**, or changing example, interaction mode or feedback mode, creates a fresh attempt and clears prediction, evidence, feedback, assessment, errors, counters and timings. A fresh session loses the previous attempt. Downloading preserves a snapshot of the current metrics; it does not create an application history or export the complete session.

The allowlist excludes prediction text, prompts, responses, source code, stdout, tracebacks, credentials, provider errors, model names and raw clock timestamps. Those exclusions apply to the JSON metrics export; Live feedback separately transmits the fields documented in [live feedback](live-feedback.md).

Durations include idle time where applicable, and the modes involve different activities. Reset does not undo exposure to earlier output. Metrics do not establish comprehension; fix-assessment questions are not a validated measure. The user's reported Stage 4 JSON download is recorded in the [development record](development-record.md), without inferring other export checks. Historical automated checks were not re-run for this documentation revision.
