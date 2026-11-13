# Live feedback

## Choosing feedback

Guided mode offers Mock and Live Gemini. Mock is the default, needs no key and displays the selected example's predefined explanation. It makes no LLM request and does not semantically assess arbitrary prediction text. Run-only mode has no feedback or assessment step.

Live Gemini uses the pinned `google-genai==3.3.0` dependency. The default model is `gemini-3.5-flash-lite`; `GEMINI_MODEL` can select another bare model ID matching `gemini-[a-z0-9][a-z0-9.-]{0,80}`. A syntactically valid ID does not establish model availability or account access. The adapter reads `GEMINI_API_KEY`, with no `GOOGLE_API_KEY` fallback. Follow the [README's hidden-input setup and clearing commands](../README.md); restart Streamlit after configuring the launch environment. No real key belongs in documentation, source or screenshots.

Free-tier availability and quotas depend on the provider and account. Unlimited or permanent free access is not promised. Check the provider's current terms before use.

## Request contents and controls

After an eligible execution, **Explain my prediction** explicitly requests feedback. Merely selecting Live Gemini, running code or causing an ordinary Streamlit rerun does not request it. A failed live attempt offers **Retry Gemini feedback**; each retry requires a deliberate click. A usable response ends retries for that attempt. There is no silent fallback to Mock.

The adapter sends a system instruction and a JSON payload to Google. The payload contains exactly:

- `task`: the selected catalogue specification.
- `provenance`: “Deliberately constructed simulation of an AI-generated Python suggestion; not a captured model response.”
- `approved_source`: the complete approved function and demonstration calls.
- `prediction`: the locked submitted prediction.
- `execution`: `stdout`, `stderr`, `exit_code`, `status` and the structured `exception_type`.

The model ID and generation settings accompany the request; the API key is used for authentication, rather than included in the prompt. The payload excludes the proposed fix, assessment question, choices, answer, rationale and mock explanation. It also excludes execution duration and exported metrics.

The instruction distinguishes task requirements, prediction and observation, asks explicitly whether execution violates a requirement and prohibits inferences about the user's understanding from one prediction. It requests the sentence “Your prediction matches the task’s intended behaviour, but the supplied code behaves differently.” when applicable. This instruction and its construction test do not guarantee compliance.

## Response boundary

The HTTP timeout is configured as 30,000 ms. SDK retry attempts are set to one, meaning one attempt with no automatic retry; automatic continuation is disabled. Output is limited to 1,024 tokens. The instruction requests at most 180 words, but the application does not enforce that word count. It rejects returned text longer than 6,000 characters.

Only the first candidate is considered. A usable response requires an unblocked prompt, a `STOP` finish reason, text content and no tool or execution parts. Thought parts are excluded from displayed text. Empty or whitespace-only text is rejected. The configured key's exact value is redacted if it appears in accepted text.

No model tools are configured, automatic function calling is disabled, and returned function, tool or code-execution parts are rejected even when mixed with text. Generated text has no application execution capability. It cannot change captured evidence or the catalogue's local grading answer. Proposed fixes are displayed for inspection, not execution.

## Failures and assessment

| Condition | Handling |
|---|---|
| Missing `GEMINI_API_KEY` | Local `missing_key` error; no provider request. |
| Invalid model syntax, or API status 400/404 | `configuration` error. |
| API status 401/403 | `authentication` error. |
| API status 429 | `rate_limit` error; explicit retry can be attempted later. |
| API status 408/504, transport timeout or `TimeoutError` | `timeout` error. |
| Transport failure or `OSError` | `network` error. |
| Missing candidate, missing content or no usable text | `empty` error. |
| Prompt blocking, safety-related finish reason or tool/execution parts | `blocked` error. |
| Other non-`STOP` finish reason or text over 6,000 characters | `incomplete` error. |
| Other API or unexpected adapter exception | Generic `provider` error. |

Messages are fixed and sanitised; raw provider exception text is not displayed. These failures leave assessment locked and allow an explicit live retry. An accepted request action counts as an attempt even if local configuration prevents an HTTP request; see [metrics](metrics.md).

Execution eligibility is checked before the adapter runs. Timeouts, launch failures, abnormal exits and unexpected execution evidence block feedback and assessment. Average's exact expected exception permits both; see the [execution boundary](execution-boundary.md). Ineligible evidence does not become eligible through retries.

## Persistence and reported limitations

The attempt, locked prediction, execution evidence, feedback, errors, counters and timings remain in Streamlit session state across ordinary reruns. Changing example, interaction mode or feedback mode, or selecting **Start new attempt**, clears the attempt and its input widgets. A fresh session loses the attempt. A downloaded export preserves only a metrics snapshot, excluding feedback text. Each attempt permits one execution and one valid assessment submission.

Do not enter personal or confidential information. Generated explanations may be wrong or make unsupported inferences. Reported List append and Average smoke tests are described in the [development record](development-record.md); revised List append feedback still inferred the user's reasoning. Successful smoke tests do not establish reliable compliance or improved comprehension. Check the provider's current terms before use.
