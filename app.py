import streamlit as st

from codelens.catalogue import get_example


st.set_page_config(page_title="CodeLens", layout="centered")
st.title("CodeLens")
st.info("Stage 1: code is displayed without execution.")

example = get_example("list_append")
st.header(example.title)
st.subheader("Task")
st.write(example.task)
st.subheader("Suggested Python code")
st.code(example.source, language="python")
