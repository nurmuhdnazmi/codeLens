import json

import streamlit as st

from codelens.catalogue import get_example
from codelens import interaction, runner


def reset_attempt():
    st.session_state["attempt"] = interaction.Attempt(
        mode=st.session_state["mode"], example_id="list_append",
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
st.title("CodeLens")
st.info("Stage 4: one run per attempt.")

if "mode" not in st.session_state:
    st.session_state["mode"] = interaction.RUN_ONLY
if "attempt" not in st.session_state:
    reset_attempt()

st.radio("Mode", interaction.MODES, key="mode", on_change=reset_attempt, horizontal=True)
st.caption("Changing modes clears the current attempt.")
st.button("Start new attempt", key="new_attempt", on_click=reset_attempt)

attempt = st.session_state["attempt"]
guided = attempt.mode == interaction.GUIDED
if guided:
    st.caption("Guided mode: predict, run, request mock feedback, then assess the proposed fix.")

example = get_example(attempt.example_id)
st.header(example.title)
st.subheader("Task")
st.write(example.task)
st.subheader("Suggested Python code")
st.code(example.source, language="python")
state_caption = st.empty()
state_caption.caption(f"Attempt state: {attempt.state}")

prediction = ""
if guided and attempt.state == "ready":
    prediction = st.text_area(
        "Predict all four printed lines", key="prediction_input",
        max_chars=interaction.MAX_PREDICTION_LENGTH,
    )
if attempt.validation_error and attempt.state == "ready":
    st.error(attempt.validation_error)

if st.button("Run approved example", key="run_example", disabled=attempt.state != "ready"):
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
    if st.button("Explain my prediction", key="explain_prediction", disabled=attempt.state != "completed") and attempt.state == "completed":
        st.session_state["attempt"] = attempt.request_feedback()
        st.rerun()

if attempt.mock_feedback_request_count:
    st.subheader("Mock feedback")
    st.caption("Mock feedback — predefined explanation; no LLM request.")
    st.caption("This template does not semantically assess free-text predictions.")
    if attempt.feedback is not None:
        st.write(attempt.feedback)
    else:
        st.warning("The predefined normal-run explanation is unavailable for this unexpected exception. Inspect the traceback above.")

if attempt.feedback is not None:
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

    if st.button("Submit assessment", key="submit_assessment", disabled=attempt.state == "verified") and attempt.state == "feedback_ready":
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
