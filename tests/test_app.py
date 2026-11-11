from pathlib import Path
from unittest.mock import Mock

import pytest

from streamlit.testing.v1 import AppTest

from codelens.catalogue import get_example
from codelens import interaction, runner


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
    assert "Stage 3" in page.info[0].value
    assert page.button(key="run_example").label == "Run approved example"
    assert not page.text_area
    assert page.session_state["attempt"].mode == interaction.RUN_ONLY
    assert page.session_state["attempt"].state == "ready"
    assert page.session_state["attempt"].result is None
    execute.assert_not_called()


def test_run_displays_real_evidence_and_reruns_preserve_it(monkeypatch):
    execute = Mock(wraps=runner.run_example)
    monkeypatch.setattr(runner, "run_example", execute)
    page = AppTest.from_file(str(APP_PATH)).run()

    page.button(key="run_example").click().run()

    assert not page.exception
    result = page.session_state["attempt"].result
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
    assert page.session_state["attempt"].result == result
    assert page.code[1].value == "[1]\n[1, 2]\n[3]\n[1, 2, 4]"
    assert execute.call_count == 1

    assert page.button(key="run_example").disabled
    page.run()

    assert not page.exception
    assert execute.call_count == 1

    page.button(key="new_attempt").click().run()
    assert page.session_state["attempt"].result is None
    assert execute.call_count == 1
    page.button(key="run_example").click().run()

    assert not page.exception
    assert execute.call_count == 2
    assert page.session_state["attempt"].result.stdout == result.stdout


@pytest.mark.parametrize("status, exit_code, message", [
    ("python_exception", 1, "Python exception"),
    ("timeout", None, "timeout"),
    ("launch_failure", None, "started"),
    ("abnormal_exit", -9, "abnormally"),
])
@pytest.mark.parametrize("mode", [interaction.RUN_ONLY, interaction.GUIDED])
def test_page_distinguishes_failures_and_shows_evidence(monkeypatch, status, exit_code, message, mode):
    result = runner.ExecutionResult(
        stdout="partial output\n", stderr="test stderr\n", exit_code=exit_code,
        status=status, elapsed_seconds=0.125,
    )
    execute = Mock(return_value=result)
    monkeypatch.setattr(runner, "run_example", execute)
    page = AppTest.from_file(str(APP_PATH)).run()
    page.radio(key="mode").set_value(mode).run()
    if mode == interaction.GUIDED:
        page.text_area(key="prediction_input").input("Submitted before failure").run()

    page.button(key="run_example").click().run()

    assert not page.exception
    assert page.session_state["attempt"].result == result
    assert page.session_state["attempt"].state == ("completed" if status == "python_exception" else "failed")
    if mode == interaction.GUIDED:
        assert page.session_state["attempt"].submitted_prediction == "Submitted before failure"
        assert page.columns[0].text[0].value == "Submitted before failure"
        assert not page.text_area
    assert [block.value for block in page.code[1:]] == ["partial output", "test stderr"]
    assert f"Status: {status}" in [text.value for text in page.markdown]
    notices = [notice.value for notice in page.error] + [notice.value for notice in page.warning]
    assert any(message in notice for notice in notices)
    assert page.button(key="run_example").disabled

    page.run()
    assert page.session_state["attempt"].result == result
    assert execute.call_count == 1

    page.button(key="new_attempt").click().run()
    assert not page.exception
    assert page.session_state["attempt"].result is None
    assert page.session_state["attempt"].state == "ready"
    assert not page.error and not page.warning
    assert len(page.code) == 1
    if mode == interaction.GUIDED:
        assert page.text_area(key="prediction_input").value == ""
    assert execute.call_count == 1


def test_page_shows_cleanup_warning_alongside_completed_evidence(monkeypatch):
    result = runner.ExecutionResult(
        stdout="completed output\n", stderr="", exit_code=0,
        status="success", elapsed_seconds=0.125,
        error="Temporary directory cleanup failed: test failure",
    )
    monkeypatch.setattr(runner, "run_example", Mock(return_value=result))
    page = AppTest.from_file(str(APP_PATH)).run()

    page.button(key="run_example").click().run()

    assert not page.exception
    assert page.code[1].value == "completed output"
    assert page.success
    assert any("cleanup failed" in notice.value for notice in page.warning)


@pytest.mark.parametrize("prediction", ["", " \n\t "])
def test_blank_guided_prediction_does_not_execute(monkeypatch, prediction):
    execute = Mock()
    monkeypatch.setattr(runner, "run_example", execute)
    page = AppTest.from_file(str(APP_PATH)).run()
    page.radio(key="mode").set_value(interaction.GUIDED).run()
    page.text_area(key="prediction_input").input(prediction).run()

    page.button(key="run_example").click().run()

    assert not page.exception
    assert page.error
    attempt = page.session_state["attempt"]
    assert attempt.state == "ready"
    assert attempt.submitted_prediction is attempt.result is None
    assert page.text_area(key="prediction_input").value == prediction
    execute.assert_not_called()


def test_guided_prediction_is_saved_before_run_and_remains_locked(monkeypatch):
    prediction = "print('this prediction must stay text')\nI expect four lists."
    real_execute = runner.run_example

    def inspect_execution(example_id):
        attempt = page.session_state["attempt"]
        assert attempt.state == "running"
        assert attempt.submitted_prediction == prediction
        return real_execute(example_id)

    execute = Mock(side_effect=inspect_execution)
    monkeypatch.setattr(runner, "run_example", execute)
    page = AppTest.from_file(str(APP_PATH)).run()
    page.radio(key="mode").set_value(interaction.GUIDED).run()
    assert "planned" in " ".join(text.value for text in page.caption)
    assert page.text_area(key="prediction_input").proto.max_chars == 2000
    page.text_area(key="prediction_input").input("Draft prediction").run()
    assert page.session_state["attempt"].submitted_prediction is None
    page.text_area(key="prediction_input").input(prediction).run()

    page.button(key="run_example").click().run()

    assert not page.exception
    attempt = page.session_state["attempt"]
    assert attempt.state == "completed"
    assert attempt.submitted_prediction == prediction
    assert attempt.result.stdout == "[1]\n[1, 2]\n[3]\n[1, 2, 4]\n"
    assert not page.text_area
    assert page.columns[0].text[0].value == prediction
    assert page.columns[1].code[0].value == "[1]\n[1, 2]\n[3]\n[1, 2, 4]"
    assert page.button(key="run_example").disabled
    execute.assert_called_once_with("list_append")

    page.session_state["prediction_input"] = "Edited after seeing output"
    page.run()
    assert not page.exception
    assert page.session_state["attempt"].submitted_prediction == prediction
    assert page.session_state["attempt"].result == attempt.result
    assert page.columns[0].text[0].value == prediction
    assert execute.call_count == 1

    page.button(key="new_attempt").click().run()
    assert not page.exception
    fresh = page.session_state["attempt"]
    assert fresh.mode == interaction.GUIDED
    assert fresh.state == "ready"
    assert fresh.result is fresh.submitted_prediction is fresh.validation_error is None
    assert page.text_area(key="prediction_input").value == ""
    assert not page.text
    assert len(page.code) == 1
    assert execute.call_count == 1


def test_reset_clears_prediction_widget_and_validation_error(monkeypatch):
    execute = Mock()
    monkeypatch.setattr(runner, "run_example", execute)
    page = AppTest.from_file(str(APP_PATH)).run()
    page.radio(key="mode").set_value(interaction.GUIDED).run()
    page.text_area(key="prediction_input").input("  ").run()
    page.button(key="run_example").click().run()
    assert page.error

    page.button(key="new_attempt").click().run()

    assert not page.exception
    assert not page.error
    assert page.session_state["attempt"].validation_error is None
    assert page.text_area(key="prediction_input").value == ""
    execute.assert_not_called()


@pytest.mark.parametrize("initial_mode", [interaction.RUN_ONLY, interaction.GUIDED])
@pytest.mark.parametrize("status", ["success", "timeout"])
def test_changing_mode_clears_prediction_and_result_without_execution(monkeypatch, initial_mode, status):
    if status == "success":
        execute = Mock(wraps=runner.run_example)
    else:
        execute = Mock(return_value=runner.ExecutionResult(
            stdout="partial\n", stderr="", exit_code=None,
            status="timeout", elapsed_seconds=2,
        ))
    monkeypatch.setattr(runner, "run_example", execute)
    page = AppTest.from_file(str(APP_PATH)).run()
    page.radio(key="mode").set_value(initial_mode).run()
    if initial_mode == interaction.GUIDED:
        page.text_area(key="prediction_input").input("My prediction").run()
    page.button(key="run_example").click().run()
    assert page.session_state["attempt"].result is not None
    other_mode = interaction.GUIDED if initial_mode == interaction.RUN_ONLY else interaction.RUN_ONLY

    page.radio(key="mode").set_value(other_mode).run()

    assert not page.exception
    fresh = page.session_state["attempt"]
    assert fresh.mode == other_mode
    assert fresh.state == "ready"
    assert fresh.submitted_prediction is fresh.result is fresh.validation_error is None
    assert not page.error and not page.warning
    assert len(page.code) == 1
    if other_mode == interaction.GUIDED:
        assert page.text_area(key="prediction_input").value == ""
    else:
        assert not page.text_area and not page.text
    execute.assert_called_once_with("list_append")


def test_changing_mode_clears_a_validation_error_and_draft(monkeypatch):
    execute = Mock()
    monkeypatch.setattr(runner, "run_example", execute)
    page = AppTest.from_file(str(APP_PATH)).run()
    page.radio(key="mode").set_value(interaction.GUIDED).run()
    page.text_area(key="prediction_input").input("\n ").run()
    page.button(key="run_example").click().run()
    assert page.error

    page.radio(key="mode").set_value(interaction.RUN_ONLY).run()
    assert not page.error and not page.text_area
    assert page.session_state["attempt"].validation_error is None
    page.radio(key="mode").set_value(interaction.GUIDED).run()
    assert not page.exception
    assert page.text_area(key="prediction_input").value == ""
    execute.assert_not_called()


def test_a_running_attempt_cannot_launch_again(monkeypatch):
    execute = Mock()
    monkeypatch.setattr(runner, "run_example", execute)
    page = AppTest.from_file(str(APP_PATH)).run()
    page.session_state["attempt"] = interaction.Attempt(
        mode=interaction.RUN_ONLY, example_id="list_append",
    ).begin()
    page.run()
    assert page.button(key="run_example").disabled

    page.run()

    assert not page.exception
    execute.assert_not_called()
