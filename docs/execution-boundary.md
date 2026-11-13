# Execution boundary

## Approved source only

`codelens/runner.py` accepts an example ID through `run_example`. `get_example` resolves it against the fixed catalogue before any subprocess is created. Unknown IDs, including strings containing Python code, raise `KeyError`. The catalogue contains List append, Average and Remove duplicates; each source includes its reviewed demonstration calls. The interface displays that complete source before execution.

Prediction text, model feedback and assessment candidates never become runner source or arguments. A proposed fix is inspected rather than executed. Repeating execution requires a new attempt, which starts a fresh subprocess; ordinary UI reruns retain the existing result.

## Subprocess configuration

The runner writes approved source as UTF-8 `example.py` in a temporary working directory. It starts the current interpreter, `sys.executable`, with `-I -X utf8 -c` and a fixed wrapper that uses `runpy.run_path`. The subprocess uses:

- `shell=False`, with arguments passed as a list.
- `stdin=DEVNULL`, preventing interactive input.
- The temporary directory as its working directory.
- `env={}`, passing an empty environment mapping rather than application credentials or API keys.
- Captured stdout and stderr, decoded as UTF-8 with replacement for invalid bytes.
- A two-second `subprocess.run` timeout and `check=False`.

A subprocess is not an OS sandbox. Isolated Python mode and an empty environment do not remove the process's filesystem or network permissions, or impose memory and output limits. Process creation may exceed the configured timeout. This boundary is intended for the fixed reviewed catalogue, not arbitrary code.

## Evidence and exception classification

`ExecutionResult` contains stdout, stderr, exit code, status, elapsed seconds, an optional error and an optional qualified exception type. Captured output remains execution evidence, separate from generated explanations.

| Status | Recognition and evidence |
|---|---|
| `success` | Exit code zero. Captured streams and the code are retained. |
| `python_exception` | The wrapper catches an `Exception`, prints its traceback to stderr and writes its qualified type to a metadata file. The parent requires exit code one and that metadata file. |
| `timeout` | `TimeoutExpired`; captured partial output is retained when available, with no recorded exit code. |
| `launch_failure` | An `OSError` preparing the directory/source or starting Python; no exit code, empty streams and a preparation/launch error. |
| `abnormal_exit` | Other nonzero exits, including unrecognised termination, or unreadable exception metadata. Captured streams and the actual exit code are retained. |

Classification depends on the fixed wrapper's metadata, not a substring in stdout or stderr. Printing an exception name does not establish `python_exception`. The wrapper catches `Exception`, not every `BaseException`: nonzero `SystemExit` and `KeyboardInterrupt` are outside this classification. A zero exit remains `success`. The marker is an internal protocol for approved code, not a security attestation for untrusted programs. If temporary-directory cleanup fails after a result exists, that evidence is retained with a cleanup warning.

Elapsed time begins after catalogue lookup, before temporary-directory preparation. It includes preparation, process launch, execution and output capture, and is recorded before normal directory cleanup. Timeout output may be incomplete, including because the child had not flushed its buffers.

## Feedback eligibility and local assessment

Guided feedback requires either successful execution for an example with no expected exception, or `python_exception` with a qualified type exactly matching the example's configured expectation. Average expects `builtins.ZeroDivisionError`. Its first call prints `4.0`; the empty-list call raises the real exception. That retained stdout and traceback allow the appropriate explanation and assessment.

Timeouts, launch failures and abnormal exits block feedback and assessment. An unexpected exception, a mismatched type or unexpected success for an example expecting an exception also blocks them. No normal-run explanation is substituted for unrelated evidence. Run-only mode displays evidence without feedback or assessment.

Usable Mock or Live Gemini feedback unlocks the selected catalogue's proposed-fix question. Grading compares the submitted choice with its fixed local answer, independently of generated claims. One valid submission locks the assessment; a new attempt clears it. Feedback-provider failures keep assessment locked, as detailed in [live feedback](live-feedback.md).

Successful execution does not establish task correctness, and one run cannot establish correctness for every input. Set iteration order is unspecified: a coincidentally matching Remove duplicates output does not establish an order-preservation guarantee. Its proposed order-preserving fix is assessed by inspection, as are the other candidates.

See the [README](../README.md) for setup and [metrics](metrics.md) for timing definitions. These descriptions were checked against source; historical application checks were not re-run for this documentation revision.
