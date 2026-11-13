import json
from pathlib import Path

import streamlit as st

from codelens.catalogue import get_example, list_examples
from codelens import interaction, runner, live_feedback


ASSETS = Path(__file__).resolve().parent / "assets"


def reset_attempt():
    st.session_state["attempt"] = interaction.Attempt(
        mode=st.session_state["mode"], example_id=st.session_state["example_id"],
        feedback_mode=st.session_state.get("feedback_mode", interaction.MOCK) if st.session_state["mode"] == interaction.GUIDED else interaction.MOCK,
    )
    st.session_state["prediction_input"] = ""
    st.session_state["assessment_choice"] = None


def show_execution_status(result):
    st.subheader("Execution evidence")
    st.write(f"Status: {result.status}")
    exit_code = result.exit_code if result.exit_code is not None else "unavailable"
    st.caption(f"Exit code: {exit_code} | Elapsed: {result.elapsed_seconds:.3f} s")

    if result.status == "success":
        st.success("Process completed (exit code 0).")
        st.caption("A successful exit does not prove that the task is satisfied.")
    elif result.status == "python_exception":
        st.warning("The program raised a Python exception. See stderr below.")
    elif result.status == "timeout":
        st.error("Execution exceeded the two-second timeout. Any output below is partial.")
    elif result.status == "launch_failure":
        st.error(result.error or "Python could not be started.")
    else:
        st.error("The process exited abnormally. This is not recognised Python exception evidence.")

    if result.error and result.status != "launch_failure":
        st.warning(result.error)

def show_stdout(result):
    st.subheader("stdout")
    st.code(result.stdout, language="text")
    if not result.stdout:
        st.caption("No stdout.")


st.set_page_config(page_title="CodeLens", layout="centered")

if "mode" not in st.session_state:
    st.session_state["mode"] = interaction.RUN_ONLY
if "example_id" not in st.session_state:
    st.session_state["example_id"] = "list_append"
if "feedback_mode" not in st.session_state:
    st.session_state["feedback_mode"] = interaction.MOCK
if "attempt" not in st.session_state:
    reset_attempt()

with st.sidebar:
    with st.container(key="sidebar_brand", gap="small"):
        st.image(str(ASSETS / "codelens-logo.svg"), width="stretch", alt="CodeLens")
        st.caption("Python practice")
    with st.container(border=True, key="mode_settings"):
        st.subheader("Practice mode")
        st.radio("Mode", interaction.MODES, key="mode", on_change=reset_attempt, label_visibility="collapsed")
        st.caption("One execution per attempt.")
st.segmented_control(
    "Example", tuple(example.id for example in list_examples()),
    format_func=lambda example_id: get_example(example_id).title,
    key="example_id", on_change=reset_attempt,
    selection_mode="single", required=True, width="stretch", wrap=True,
)
st.caption("Choose an example and a mode to begin. Changing either clears your current attempt.")
with st.expander("How to use CodeLens", expanded=False):
    st.markdown(
        "1. **Run-only:** Select **Run approved example** and inspect its output or traceback.\n"
        "2. **Predict–Explain–Verify:** Enter your prediction and select **Run approved example** "
        "to submit it and execute the code. Select **Explain my prediction** to request feedback, "
        "then assess the proposed fix and select **Submit assessment**.\n"
        "3. **Repeat:** Select **Start new attempt** to begin again.\n"
        "4. **Metrics:** Open **Current-attempt metrics** to inspect or download the interaction record."
    )
    st.markdown(
        "Reviewer note: To review the complete guided flow without an API key, select "
        "Predict–Explain–Verify with Mock feedback. Try all three examples and inspect "
        "the metrics after an assessment."
    )
    st.caption("Changing feedback mode clears your current attempt.")

attempt = st.session_state["attempt"]
guided = attempt.mode == interaction.GUIDED
if guided:
    with st.sidebar:
        with st.container(border=True, key="feedback_settings"):
            st.subheader("Feedback")
            st.radio("Feedback", interaction.FEEDBACK_MODES, key="feedback_mode", on_change=reset_attempt, label_visibility="collapsed")
            st.caption("Changing feedback mode clears your current attempt.")
    if attempt.feedback_mode == interaction.MOCK:
        st.caption("Guided mode: predict, run, request mock feedback, then assess the proposed fix.")
    else:
        st.caption("Guided mode: predict, run, request live Gemini feedback, then assess the proposed fix.")
        st.warning("Live Gemini sends the task, approved source and demonstration calls, locked prediction and execution evidence to Google. Do not enter personal or confidential information.")

with st.sidebar:
    st.button("Start new attempt", key="new_attempt", on_click=reset_attempt, type="secondary", width="stretch", icon=":material/restart_alt:")

example = get_example(attempt.example_id)
st.title(example.title)
with st.container(border=True, key="task_brief"):
    st.subheader("Task")
    st.write(example.task)
with st.container(border=True, key="code_review"):
    st.subheader("Suggested Python code")
    st.code(example.source, language="python")
    state_caption = st.empty()
    state_caption.caption(f"Attempt state: {attempt.state}")

    prediction = ""
    if guided and attempt.state == "ready":
        prediction = st.text_area(
            example.prediction_prompt, key="prediction_input",
            max_chars=interaction.MAX_PREDICTION_LENGTH,
        )
    if attempt.validation_error and attempt.state == "ready":
        st.error(attempt.validation_error)

    if st.button(
        "Run approved example", key="run_example", disabled=attempt.state != "ready",
        type="primary" if attempt.state == "ready" else "secondary", width="stretch",
    ):
        if attempt.state == "ready":
            pending = attempt.begin(prediction)
            st.session_state["attempt"] = pending
            if pending.state == "running":
                state_caption.caption("Attempt state: running")
                with st.spinner("Running approved example..."):
                    result = runner.run_example(pending.example_id)
                    st.session_state["attempt"] = pending.finish(result)
            st.rerun()

if attempt.result is not None:
    with st.container(border=True, key="execution_evidence"):
        show_execution_status(attempt.result)
        if guided:
            prediction_column, evidence_column = st.columns(2)
            with prediction_column:
                st.subheader("Submitted prediction")
                st.code(attempt.submitted_prediction, language="text")
            with evidence_column:
                show_stdout(attempt.result)
        else:
            show_stdout(attempt.result)

        st.subheader("stderr / traceback")
        if attempt.result.stderr:
            st.code(attempt.result.stderr, language="text")
        else:
            st.caption("No stderr.")

if guided and attempt.result is not None and attempt.result.status in ("success", "python_exception"):
    with st.container(border=True, key="feedback"):
        st.subheader("Mock feedback" if attempt.feedback_mode == interaction.MOCK else "Live Gemini feedback")
        request_allowed = attempt.state == "completed" or (attempt.feedback_mode == interaction.LIVE_GEMINI and attempt.state == "feedback_failed")
        request_label = "Retry Gemini feedback" if attempt.state == "feedback_failed" else "Explain my prediction"
        if st.button(
            request_label, key="explain_prediction", disabled=not request_allowed,
            type="primary" if request_allowed else "secondary", width="stretch",
        ) and request_allowed:
            pending = attempt.request_feedback()
            st.session_state["attempt"] = pending
            if pending.state == "feedback_requesting":
                state_caption.caption("Attempt state: feedback_requesting")
                with st.spinner("Requesting Gemini feedback..."):
                    outcome = live_feedback.generate_feedback(pending.example_id, pending.submitted_prediction, pending.result)
                    st.session_state["attempt"] = pending.complete_live_feedback(outcome)
            st.rerun()

        if attempt.mock_feedback_request_count:
            st.caption("Mock feedback — predefined explanation; no LLM request.")
            st.caption("This template does not semantically assess free-text predictions.")
            if attempt.feedback is not None:
                st.write(attempt.feedback)
            else:
                st.warning("The predefined explanation is unavailable for this execution evidence. Inspect the output and traceback above.")

        if guided and attempt.feedback_mode == interaction.LIVE_GEMINI and (attempt.live_feedback_request_attempts or attempt.state == "feedback_unavailable"):
            if attempt.feedback_model:
                st.caption(f"Provider: Google Gemini | Model: {attempt.feedback_model}")
            st.caption("Generated explanations may be wrong. Inspect them against the execution evidence.")
            if attempt.feedback is not None:
                st.markdown(attempt.feedback)
            elif attempt.feedback_error:
                st.error(live_feedback.ERROR_MESSAGES.get(attempt.feedback_error, live_feedback.ERROR_MESSAGES["provider"]))
            elif attempt.state == "feedback_unavailable":
                st.warning("Feedback is unavailable for this unexpected execution evidence. Inspect the output and traceback above.")

if attempt.feedback is not None:
    with st.container(border=True, key="fix_assessment"):
        question = example.verification
        st.subheader("Assess a proposed fix")
        st.code(question.candidate_source, language="python")
        st.caption("For inspection only; this replacement is not executed.")
        if attempt.state == "verified":
            st.write(question.question)
            st.text(f"Submitted assessment: {attempt.assessment_choice}")
        else:
            selection = st.radio(question.question, question.choices, index=None, key="assessment_choice")
            if attempt.validation_error:
                st.error(attempt.validation_error)

        if st.button(
            "Submit assessment", key="submit_assessment", disabled=attempt.state == "verified",
            type="primary" if attempt.state == "feedback_ready" else "secondary", width="stretch",
        ) and attempt.state == "feedback_ready":
            st.session_state["attempt"] = attempt.submit_assessment(selection)
            st.rerun()

        if attempt.state == "verified":
            if attempt.verification_correct:
                st.success("Correct for this question.")
            elif attempt.assessment_choice == "Not sure":
                st.info("Not sure recorded.")
            else:
                st.warning("Incorrect for this question.")
            st.write(f"Catalogue answer: {question.answer}")
            st.write(question.rationale)
            st.caption("This single assessment does not establish comprehension or learning gains.")

with st.expander("Current-attempt metrics"):
    metrics = attempt.metrics()
    st.json(metrics)
    st.download_button(
        "Download metrics JSON", data=json.dumps(metrics, indent=2),
        file_name="codelens-attempt.json", mime="application/json", key="metrics_export",
    )
    st.caption("Reset or refresh loses this attempt unless exported. Times include idle time; the modes involve different activities. These are interaction records, not evidence of improved comprehension.")
