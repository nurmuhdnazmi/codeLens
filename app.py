import streamlit as st

from codelens.catalogue import get_example
from codelens import interaction, runner


def reset_attempt():
    st.session_state["attempt"] = interaction.Attempt(
        mode=st.session_state["mode"], example_id="list_append",
    )
    st.session_state["prediction_input"] = ""


def show_evidence(result):
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

    st.subheader("stdout")
    if result.stdout:
        st.code(result.stdout, language="text")
    else:
        st.caption("No stdout.")

    st.subheader("stderr / traceback")
    if result.stderr:
        st.code(result.stderr, language="text")
    else:
        st.caption("No stderr.")


st.set_page_config(page_title="CodeLens", layout="centered")
st.title("CodeLens")
st.info("Stage 3: one run per attempt.")

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
    st.caption("Guided mode supports prediction and execution only. Explanation and verification are planned.")

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
if attempt.validation_error:
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
    if guided:
        prediction_column, evidence_column = st.columns(2)
        with prediction_column:
            st.subheader("Submitted prediction")
            st.text(attempt.submitted_prediction)
        with evidence_column:
            show_evidence(attempt.result)
    else:
        show_evidence(attempt.result)
