from pathlib import Path
from unittest.mock import Mock

import pytest

from streamlit.testing.v1 import AppTest

from codelens.catalogue import get_example
from codelens import runner


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_page_displays_complete_source_without_executing(monkeypatch):
    example = get_example("list_append")
    execute = Mock(wraps=runner.run_example)
    monkeypatch.setattr(runner, "run_example", execute)

    page = AppTest.from_file(str(APP_PATH)).run()

    assert not page.exception
    assert page.title[0].value == "CodeLens"
    assert example.title in [heading.value for heading in page.header]
    assert example.task in [text.value for text in page.markdown]
    assert len(page.code) == 1
    # Streamlit trims the final newline.
    assert page.code[0].value == example.source.removesuffix("\n")
    assert "Stage 2" in page.info[0].value
    assert page.button[0].label == "Run approved example"
    assert not page.text_area
    assert "execution_result" not in page.session_state
    execute.assert_not_called()


def test_run_displays_real_evidence_and_reruns_preserve_it(monkeypatch):
    execute = Mock(wraps=runner.run_example)
    monkeypatch.setattr(runner, "run_example", execute)
    page = AppTest.from_file(str(APP_PATH)).run()

    page.button[0].click().run()

    assert not page.exception
    result = page.session_state["execution_result"]
    assert result.stdout == "[1]\n[1, 2]\n[3]\n[1, 2, 4]\n"
    assert result.stderr == ""
    assert result.status == "success"
    assert page.code[1].value == "[1]\n[1, 2]\n[3]\n[1, 2, 4]"
    assert "Status: success" in [text.value for text in page.markdown]
    assert any("Exit code: 0" in text.value for text in page.caption)
    assert any("Elapsed:" in text.value for text in page.caption)
    assert "No stderr." in [text.value for text in page.caption]
    execute.assert_called_once_with("list_append")

    page.run()

    assert not page.exception
    assert page.session_state["execution_result"] == result
    assert page.code[1].value == "[1]\n[1, 2]\n[3]\n[1, 2, 4]"
    assert execute.call_count == 1

    page.button[0].click().run()

    assert not page.exception
    assert execute.call_count == 2
    assert page.session_state["execution_result"].stdout == result.stdout


@pytest.mark.parametrize("status, exit_code, message", [
    ("python_exception", 1, "Python exception"),
    ("timeout", None, "timeout"),
    ("launch_failure", None, "started"),
    ("abnormal_exit", -9, "abnormally"),
])
def test_page_distinguishes_failures_and_shows_evidence(monkeypatch, status, exit_code, message):
    result = runner.ExecutionResult(
        stdout="partial output\n", stderr="test stderr\n", exit_code=exit_code,
        status=status, elapsed_seconds=0.125,
    )
    monkeypatch.setattr(runner, "run_example", Mock(return_value=result))
    page = AppTest.from_file(str(APP_PATH)).run()

    page.button[0].click().run()

    assert not page.exception
    assert page.session_state["execution_result"] == result
    assert [block.value for block in page.code[1:]] == ["partial output", "test stderr"]
    assert f"Status: {status}" in [text.value for text in page.markdown]
    notices = [notice.value for notice in page.error] + [notice.value for notice in page.warning]
    assert any(message in notice for notice in notices)


def test_page_shows_cleanup_warning_alongside_completed_evidence(monkeypatch):
    result = runner.ExecutionResult(
        stdout="completed output\n", stderr="", exit_code=0,
        status="success", elapsed_seconds=0.125,
        error="Temporary directory cleanup failed: test failure",
    )
    monkeypatch.setattr(runner, "run_example", Mock(return_value=result))
    page = AppTest.from_file(str(APP_PATH)).run()

    page.button[0].click().run()

    assert not page.exception
    assert page.code[1].value == "completed output"
    assert page.success
    assert any("cleanup failed" in notice.value for notice in page.warning)
