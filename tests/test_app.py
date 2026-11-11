from pathlib import Path

from streamlit.testing.v1 import AppTest

from codelens.catalogue import get_example


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_static_page_displays_the_approved_task_and_source():
    example = get_example("list_append")

    page = AppTest.from_file(str(APP_PATH)).run()

    assert not page.exception
    assert page.title[0].value == "CodeLens"
    assert example.title in [heading.value for heading in page.header]
    assert example.task in [text.value for text in page.markdown]
    assert len(page.code) == 1
    # Streamlit trims the final newline.
    assert page.code[0].value == example.source.removesuffix("\n")
    assert "Stage 1" in page.info[0].value
    assert not page.button
    assert not page.text_area
