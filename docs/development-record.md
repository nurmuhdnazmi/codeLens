# Development record

CodeLens was developed for the University of Birmingham's Intelligent Interactive Systems Assignment 2, following the Assignment 1 review of code comprehension and verification effort. ChatGPT supported the concept and earlier reference prototype. Codex assisted structure, implementation, tests and debugging. Attribution here follows the conversation, not Git author names.

## Stages and evidence

All six supplied commits resolve in the available Git history. The table records implementation and evidence sources; it does not report a new application test run.

| Stage | Significant change and reason | Implementation and checking | Evidence | Verified commit |
|---|---|---|---|---|
| 1 | Static catalogue and interface, establishing the task and complete suggested code before execution. | Codex implemented the foundation and reported automated checks. | Committed catalogue and interface tests. | [020af95](https://github.com/nurmuhdnazmi/codeLens/commit/020af955ec4a3f07a118ce5873bb7c5da8c5bae4) |
| 2 | Approved subprocess execution and captured evidence, allowing actual behaviour to be inspected. | Codex implemented the runner and reported automated checks. | Committed runner and interface tests cover output, repeat runs, rejected IDs and failure paths. | [93a37a1](https://github.com/nurmuhdnazmi/codeLens/commit/93a37a12cf7851815a492f07d82697a49f6f710b) |
| 3 | Run-only and guided modes, locked predictions and one execution per attempt, preserving the prediction before evidence appears. | Codex implemented attempt state and reported automated checks. | Committed interaction and interface tests exercise validation, persistence and resets. | [6654dfc](https://github.com/nurmuhdnazmi/codeLens/commit/6654dfc05808171aa915cb6cce34ecde9eaebc16) |
| 4 | Predefined mock feedback, one local fix assessment and metrics, completing the guided flow without a provider request. | Codex implemented the flow and reported automated checks. I downloaded the metrics JSON and supplied it for inspection. | Committed assessment, timing and export tests; my reported download establishes that action only. | [5ba6227](https://github.com/nurmuhdnazmi/codeLens/commit/5ba6227713d2e9590ad9f34635aa3d4ebc191249) |
| 5 | Average and Remove duplicates, adding an expected exception and a requirement that successful execution alone cannot establish. | Codex implemented the examples and reported automated checks. I reported that Stage 5 browser checks passed. | Committed real-execution, feedback, assessment and reset tests. The general browser report does not establish individual manual results. | [761906b](https://github.com/nurmuhdnazmi/codeLens/commit/761906b72013bac2a811ff21bf5042cc265b7946) |
| 6 | Optional live Gemini explanations, explicit requests and retries, retaining local execution and grading. | Codex implemented the adapter and revised its instructions. I chose the free-tier integration, configured access, tested List append and Average, and retested the revision. ChatGPT reviewed the shared responses. | Committed adapter doubles and interaction/interface tests; reported live results below. The diff includes the revised instructions and focused prompt test. | [ca59b54](https://github.com/nurmuhdnazmi/codeLens/commit/ca59b5486069c82e2ff3c91d72c521d856de6b5f) |

Stage 6 is the Gemini integration commit, not a final submission reference.

## Reported checks and live review

Earlier Codex messages reported 170 passing tests after the prompt revision. Separate earlier Codex reports recorded no broken dependencies and successful mypy checks for six source files. These are historical reports, not re-run for this documentation revision. They are not one freshly executed verification run; mypy is not included in the project's declared development dependencies.

The committed runner tests include real subprocess execution of all three examples. Controlled doubles cover failure paths and Gemini responses; the Streamlit tests exercise interface state. Their presence was inspected for this revision, without executing them or making a live request.

The first live List append response was labelled `gemini-3.5-flash-lite`. Its output comparison and mutable-default explanation were accurate. ChatGPT's review identified an unsupported inference about my understanding and an insufficiently explicit comparison with the task. Codex revised the instructions to separate requirements, prediction and observation, explicitly identify task violations and avoid inferring knowledge from one prediction.

I retested the revision. Revised List append feedback identified the task violation but still made an unsupported inference about my reasoning. Average feedback correctly explained stdout `4.0`, the `ZeroDivisionError` and the failure to return `None`. These reported smoke tests establish neither reliable instruction compliance nor improved comprehension.

The Stage 6 diff contains `test_prompt_distinguishes_task_prediction_and_observation_without_judging_user` in `tests/test_live_feedback.py`. It checks the constructed instructions and separated request fields, not whether a model follows them.

No live Remove duplicates result is reported. Manual rerun-count, assessment-locking and fresh-install outcomes are not recorded here. No user-evaluation results are reported. Absence of a reported result does not establish that a check was not performed.

## Documentation revision

This revision checks source consistency, local Markdown targets, commit references, accidental credentials and whitespace. Application tests, dependency checks, mypy, the app and live requests were not run. Setup commands are instructions, not newly verified installation results; Windows execution remains unverified here.

See the [README](../README.md), [live feedback](live-feedback.md), [execution boundary](execution-boundary.md) and [metrics definitions](metrics.md).
