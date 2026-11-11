import streamlit as st

from codelens.catalogue import get_example
from codelens import runner


st.set_page_config(page_title="CodeLens", layout="centered")
st.title("CodeLens")
st.info("Stage 2: run the approved example to inspect its output.")

example = get_example("list_append")
st.header(example.title)
st.subheader("Task")
st.write(example.task)
st.subheader("Suggested Python code")
st.code(example.source, language="python")

if st.button("Run approved example"):
    with st.spinner("Running approved example..."):
        st.session_state["execution_result"] = runner.run_example(example.id)

result = st.session_state.get("execution_result")
if result is not None:
    st.subheader("Execution evidence")
    st.write(f"Status: {result.status}")
    exit_code = result.exit_code if result.exit_code is not None else "unavailable"
    st.caption(f"Exit code: {exit_code} | Elapsed: {result.elapsed_seconds:.3f} s")

    if result.status == "success":
        st.success("Execution completed.")
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
