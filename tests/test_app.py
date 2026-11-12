from pathlib import Path
import json
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
    assert "Stage 5" in page.info[0].value
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
        assert page.columns[0].code[0].value == "Submitted before failure"
        assert not page.text_area
    expected_blocks = ["partial output", "test stderr"]
    if mode == interaction.GUIDED:
        expected_blocks.insert(0, "Submitted before failure")
    assert [block.value for block in page.code[1:]] == expected_blocks
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
    assert "mock feedback" in " ".join(text.value for text in page.caption)
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
    assert page.columns[0].code[0].value == prediction
    assert page.columns[1].code[0].value == "[1]\n[1, 2]\n[3]\n[1, 2, 4]"
    assert page.button(key="run_example").disabled
    execute.assert_called_once_with("list_append")

    page.session_state["prediction_input"] = "Edited after seeing output"
    page.run()
    assert not page.exception
    assert page.session_state["attempt"].submitted_prediction == prediction
    assert page.session_state["attempt"].result == attempt.result
    assert page.columns[0].code[0].value == prediction
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


def guided_page(monkeypatch):
    execute = Mock(wraps=runner.run_example)
    monkeypatch.setattr(runner, "run_example", execute)
    page = AppTest.from_file(str(APP_PATH)).run()
    page.radio(key="mode").set_value(interaction.GUIDED).run()
    page.text_area(key="prediction_input").input("My four-line prediction").run()
    return page, execute


def test_feedback_controls_require_guided_completed_evidence(monkeypatch):
    page, execute = guided_page(monkeypatch)
    assert "explain_prediction" not in [button.key for button in page.button]
    page.radio(key="mode").set_value(interaction.RUN_ONLY).run()
    page.button(key="run_example").click().run()
    assert not page.exception
    assert "explain_prediction" not in [button.key for button in page.button]
    assert "submit_assessment" not in [button.key for button in page.button]
    execute.assert_called_once_with("list_append")


@pytest.mark.parametrize("status", ["timeout", "launch_failure", "abnormal_exit"])
def test_runner_failures_do_not_unlock_feedback_or_verification(monkeypatch, status):
    page, execute = guided_page(monkeypatch)
    execute.return_value = runner.ExecutionResult(
        stdout="partial", stderr="failure details", exit_code=None,
        status=status, elapsed_seconds=2,
    )
    page.button(key="run_example").click().run()
    assert not page.exception
    assert page.session_state["attempt"].state == "failed"
    assert "explain_prediction" not in [button.key for button in page.button]
    assert "submit_assessment" not in [button.key for button in page.button]
    assert page.session_state["attempt"].metrics()["total_duration_seconds"] is None
    execute.assert_called_once_with("list_append")


def test_unexpected_exception_feedback_is_unavailable_and_traceback_stays_visible(monkeypatch):
    page, execute = guided_page(monkeypatch)
    execute.return_value = runner.ExecutionResult(
        stdout="", stderr="Traceback: ValueError: unexpected", exit_code=1,
        status="python_exception", elapsed_seconds=0.1,
    )
    page.button(key="run_example").click().run()
    page.button(key="explain_prediction").click().run()
    assert not page.exception
    assert page.session_state["attempt"].state == "feedback_unavailable"
    assert any("unavailable" in notice.value for notice in page.warning)
    assert "Traceback: ValueError: unexpected" in [block.value for block in page.code]
    assert get_example("list_append").mock_explanation not in [text.value for text in page.markdown]
    assert "submit_assessment" not in [button.key for button in page.button]
    execute.assert_called_once_with("list_append")


@pytest.mark.parametrize("choice, correct, message", [
    ("Meets the task", True, "Correct for this question"),
    ("Does not meet the task", False, "Incorrect for this question"),
    ("Not sure", False, "Not sure recorded"),
])
def test_complete_guided_flow_preserves_feedback_and_locks_assessment(monkeypatch, choice, correct, message):
    page, execute = guided_page(monkeypatch)
    example = get_example("list_append")
    page.button(key="run_example").click().run()
    assert example.verification.candidate_source.removesuffix("\n") not in [block.value for block in page.code]
    assert page.columns[0].subheader[0].value == "Submitted prediction"
    assert page.columns[1].subheader[0].value == "stdout"
    assert page.columns[0].code[0].proto.language == page.columns[1].code[0].proto.language == "text"

    page.button(key="explain_prediction").click().run()

    assert not page.exception
    explained = page.session_state["attempt"]
    assert explained.state == "feedback_ready"
    assert explained.feedback == example.mock_explanation
    assert "Mock feedback — predefined explanation; no LLM request." in [text.value for text in page.caption]
    assert any("does not semantically assess" in text.value for text in page.caption)
    assert example.mock_explanation in [text.value for text in page.markdown]
    assert example.verification.candidate_source.removesuffix("\n") in [block.value for block in page.code]
    assert page.radio(key="assessment_choice").value is None
    assert tuple(page.radio(key="assessment_choice").options) == example.verification.choices
    assert example.verification.rationale not in [text.value for text in page.markdown]

    page.button(key="submit_assessment").click().run()
    assert page.error
    assert page.session_state["attempt"].verification_submission_count == 0
    assert page.session_state["attempt"].verification_correct is None
    page.run()
    assert page.session_state["attempt"].mock_feedback_request_count == 1
    assert page.session_state["attempt"].feedback == explained.feedback
    assert page.session_state["attempt"].verification_started_at == explained.verification_started_at

    page.radio(key="assessment_choice").set_value(choice).run()
    page.button(key="submit_assessment").click().run()

    assert not page.exception
    verified = page.session_state["attempt"]
    assert verified.state == "verified"
    assert verified.assessment_choice == choice
    assert verified.verification_correct is correct
    assert verified.verification_submission_count == 1
    assert not page.error
    assert not [radio for radio in page.radio if radio.key == "assessment_choice"]
    notices = list(page.success) + list(page.warning) + list(page.info)
    assert any(message in notice.value for notice in notices)
    assert example.verification.rationale in [text.value for text in page.markdown]
    assert example.verification.candidate_source.removesuffix("\n") in [block.value for block in page.code]
    assert page.button(key="submit_assessment").disabled
    assert page.button(key="explain_prediction").disabled
    metrics = json.loads(page.json[0].value)
    assert metrics == verified.metrics()
    assert metrics["execution_count"] == metrics["mock_feedback_request_count"] == metrics["verification_submission_count"] == 1
    assert metrics["total_duration_seconds"] is not None

    page.run()
    assert page.session_state["attempt"] == verified
    assert json.loads(page.json[0].value) == metrics
    execute.assert_called_once_with("list_append")


@pytest.mark.parametrize("action", ["reset", "mode"])
@pytest.mark.parametrize("submit", [False, True])
def test_reset_or_mode_change_clears_feedback_selection_and_metrics(monkeypatch, action, submit):
    page, execute = guided_page(monkeypatch)
    page.button(key="run_example").click().run()
    page.button(key="explain_prediction").click().run()
    page.radio(key="assessment_choice").set_value("Meets the task").run()
    if submit:
        page.button(key="submit_assessment").click().run()

    if action == "reset":
        page.button(key="new_attempt").click().run()
    else:
        page.radio(key="mode").set_value(interaction.RUN_ONLY).run()
        page.radio(key="mode").set_value(interaction.GUIDED).run()

    assert not page.exception
    fresh = page.session_state["attempt"]
    assert fresh.state == "ready"
    assert fresh.feedback is fresh.assessment_choice is fresh.verification_correct is None
    assert fresh.execution_count == fresh.mock_feedback_request_count == fresh.verification_submission_count == 0
    assert fresh.prediction_duration_seconds is fresh.verification_duration_seconds is fresh.total_duration_seconds is None
    assert page.text_area(key="prediction_input").value == ""
    assert "submit_assessment" not in [button.key for button in page.button]
    assert len(page.code) == 1
    execute.assert_called_once_with("list_append")

    page.text_area(key="prediction_input").input("New prediction").run()
    page.button(key="run_example").click().run()
    page.button(key="explain_prediction").click().run()
    assert not page.exception
    assert page.radio(key="assessment_choice").value is None
    assert execute.call_count == 2


def test_download_receives_only_current_metrics_json(monkeypatch):
    import streamlit as st

    real_download = st.download_button
    downloads = []

    def record_download(label, data, **options):
        downloads.append(json.loads(data))
        return real_download(label, data, **options)

    monkeypatch.setattr(st, "download_button", record_download)
    page, execute = guided_page(monkeypatch)
    page.button(key="run_example").click().run()
    page.button(key="explain_prediction").click().run()
    page.radio(key="assessment_choice").set_value("Meets the task").run()
    page.button(key="submit_assessment").click().run()
    assert not page.exception
    assert downloads[-1] == page.session_state["attempt"].metrics()
    assert "My four-line prediction" not in json.dumps(downloads[-1])
    assert "Meets the task" not in json.dumps(downloads[-1])
    execute.assert_called_once_with("list_append")


@pytest.mark.parametrize("example_id, answer", [
    ("list_append", "Meets the task"),
    ("average", "Does not meet the task"),
    ("remove_duplicates", "Meets the task"),
])
@pytest.mark.parametrize("mode", [interaction.RUN_ONLY, interaction.GUIDED])
def test_both_modes_execute_each_example_and_guided_flow_completes(monkeypatch, example_id, answer, mode):
    execute = Mock(wraps=runner.run_example)
    monkeypatch.setattr(runner, "run_example", execute)
    page = AppTest.from_file(str(APP_PATH)).run()
    page.selectbox(key="example_id").set_value(example_id).run()
    page.radio(key="mode").set_value(mode).run()
    example = get_example(example_id)
    assert example.task in [text.value for text in page.markdown]
    assert page.code[0].value == example.source.removesuffix("\n")
    if mode == interaction.GUIDED:
        assert page.text_area(key="prediction_input").label == example.prediction_prompt
        page.text_area(key="prediction_input").input("My prediction for this example").run()
    else:
        assert not page.text_area

    page.button(key="run_example").click().run()

    assert not page.exception
    attempt = page.session_state["attempt"]
    assert attempt.example_id == example_id
    assert attempt.state == "completed"
    assert attempt.result.stdout.removesuffix("\n") in [block.value for block in page.code]
    if example_id == "average":
        assert attempt.result.stdout == "4.0\n"
        assert attempt.result.exception_type == "builtins.ZeroDivisionError"
        assert "ZeroDivisionError" in page.code[-1].value
    if mode == interaction.RUN_ONLY:
        assert "explain_prediction" not in [button.key for button in page.button]
        assert "submit_assessment" not in [button.key for button in page.button]
    else:
        page.button(key="explain_prediction").click().run()
        assert not page.exception
        assert page.session_state["attempt"].feedback == example.mock_explanation
        assert example.mock_explanation in [text.value for text in page.markdown]
        assert "Mock feedback — predefined explanation; no LLM request." in [text.value for text in page.caption]
        assert page.radio(key="assessment_choice").value is None
        page.radio(key="assessment_choice").set_value(answer).run()
        page.button(key="submit_assessment").click().run()
        assert not page.exception
        verified = page.session_state["attempt"]
        assert verified.state == "verified"
        assert verified.verification_correct is True
        assert verified.assessment_choice == answer
        assert example.verification.rationale in [text.value for text in page.markdown]
        page.run()
        assert page.session_state["attempt"] == verified
    execute.assert_called_once_with(example_id)


@pytest.mark.parametrize("phase", ["validation_error", "selected", "verified", "runner_failure"])
def test_changing_example_clears_the_entire_attempt_and_visible_values(monkeypatch, phase):
    clock = [10.0]
    monkeypatch.setattr(interaction, "monotonic", lambda: clock[0])
    page, execute = guided_page(monkeypatch)
    if phase == "validation_error":
        page.text_area(key="prediction_input").input(" ").run()
        page.button(key="run_example").click().run()
        assert page.error
    else:
        if phase == "runner_failure":
            execute.return_value = runner.ExecutionResult(
                stdout="stale partial output", stderr="stale failure", exit_code=None,
                status="timeout", elapsed_seconds=2,
            )
        page.button(key="run_example").click().run()
        if phase != "runner_failure":
            page.button(key="explain_prediction").click().run()
            page.radio(key="assessment_choice").set_value("Meets the task").run()
            if phase == "verified":
                page.button(key="submit_assessment").click().run()

    calls_before_change = execute.call_count
    clock[0] = 50.0
    page.selectbox(key="example_id").set_value("average").run()

    assert not page.exception
    fresh = page.session_state["attempt"]
    assert fresh.example_id == "average" and fresh.mode == interaction.GUIDED
    assert fresh.state == "ready"
    assert fresh.submitted_prediction is fresh.result is fresh.feedback is fresh.assessment_choice is None
    assert fresh.verification_correct is fresh.validation_error is None
    assert fresh.execution_count == fresh.mock_feedback_request_count == fresh.verification_submission_count == 0
    assert fresh.created_at == 50.0
    assert fresh.verification_started_at is fresh.prediction_duration_seconds is fresh.verification_duration_seconds is fresh.total_duration_seconds is None
    assert fresh.metrics()["execution_duration_seconds"] is None
    assert page.text_area(key="prediction_input").value == ""
    assert page.code[0].value == get_example("average").source.removesuffix("\n")
    assert len(page.code) == 1
    assert not page.error and not page.warning
    assert execute.call_count == calls_before_change
    assert "submit_assessment" not in [button.key for button in page.button]

    page.selectbox(key="example_id").set_value("list_append").run()
    assert not page.exception
    assert page.text_area(key="prediction_input").value == ""
    if phase == "runner_failure":
        execute.return_value = runner.ExecutionResult(stdout="fresh output", stderr="", exit_code=0, status="success", elapsed_seconds=0.01)
    page.text_area(key="prediction_input").input("Fresh prediction").run()
    page.button(key="run_example").click().run()
    page.button(key="explain_prediction").click().run()
    assert not page.exception
    assert page.radio(key="assessment_choice").value is None


def test_mode_change_and_reset_keep_the_selected_example(monkeypatch):
    execute = Mock(wraps=runner.run_example)
    monkeypatch.setattr(runner, "run_example", execute)
    page = AppTest.from_file(str(APP_PATH)).run()
    page.selectbox(key="example_id").set_value("average").run()
    page.button(key="run_example").click().run()
    page.radio(key="mode").set_value(interaction.GUIDED).run()
    assert not page.exception
    assert page.session_state["attempt"].example_id == "average"
    assert page.session_state["attempt"].result is None
    page.text_area(key="prediction_input").input("Draft prediction").run()
    page.button(key="new_attempt").click().run()
    assert not page.exception
    assert page.selectbox(key="example_id").value == "average"
    assert page.session_state["attempt"].example_id == "average"
    assert page.text_area(key="prediction_input").value == ""
    execute.assert_called_once_with("average")
