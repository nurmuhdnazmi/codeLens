from dataclasses import FrozenInstanceError, replace
import json

import pytest

from codelens import interaction
from codelens import runner
from codelens.live_feedback import FeedbackOutcome
from codelens.runner import ExecutionResult
from codelens.catalogue import get_example


def result_with_status(status):
    return ExecutionResult(
        stdout="actual output\n", stderr="", exit_code=0 if status == "success" else 1,
        status=status, elapsed_seconds=0.01,
    )


@pytest.mark.parametrize("prediction", ["", " ", "\n\t "])
def test_blank_guided_prediction_does_not_start_an_attempt(prediction):
    attempt = interaction.Attempt(mode=interaction.GUIDED, example_id="list_append")

    rejected = attempt.begin(prediction)

    assert rejected.state == "ready"
    assert rejected.submitted_prediction is None
    assert rejected.result is None
    assert rejected.validation_error


def test_guided_prediction_is_saved_exactly_before_execution():
    prediction = "First line: a list.\nOther lines: I am unsure.  "
    attempt = interaction.Attempt(mode=interaction.GUIDED, example_id="list_append")

    running = attempt.begin(prediction)

    assert running.state == "running"
    assert running.mode == interaction.GUIDED
    assert running.example_id == "list_append"
    assert running.submitted_prediction == prediction
    assert running.result is None
    assert running.validation_error is None


def test_prediction_length_is_checked_by_the_state_model():
    attempt = interaction.Attempt(mode=interaction.GUIDED, example_id="list_append")

    assert attempt.begin("x" * 2000).state == "running"
    rejected = attempt.begin("x" * 2001)
    assert rejected.state == "ready"
    assert rejected.validation_error
    assert rejected.submitted_prediction is None


def test_run_only_does_not_store_or_require_a_prediction():
    attempt = interaction.Attempt(mode=interaction.RUN_ONLY, example_id="list_append")

    running = attempt.begin("ignored draft")

    assert running.state == "running"
    assert running.submitted_prediction is None


@pytest.mark.parametrize("status, state", [
    ("success", "completed"),
    ("python_exception", "completed"),
    ("timeout", "failed"),
    ("launch_failure", "failed"),
    ("abnormal_exit", "failed"),
])
def test_result_categories_set_the_attempt_state(status, state):
    running = interaction.Attempt(mode=interaction.GUIDED, example_id="list_append").begin("My prediction")
    result = result_with_status(status)

    finished = running.finish(result)

    assert finished.state == state
    assert finished.result == result
    assert finished.submitted_prediction == "My prediction"
    assert finished.validation_error is None


def test_an_attempt_cannot_start_again_or_rewrite_a_submitted_prediction():
    running = interaction.Attempt(mode=interaction.GUIDED, example_id="list_append").begin("Original prediction")
    finished = running.finish(result_with_status("success"))

    for attempt in (running, finished):
        with pytest.raises(ValueError):
            attempt.begin("Changed after seeing output")
    with pytest.raises(FrozenInstanceError):
        finished.submitted_prediction = "Changed"


def test_only_a_running_attempt_can_accept_a_result():
    ready = interaction.Attempt(mode=interaction.RUN_ONLY, example_id="list_append")
    result = result_with_status("success")

    with pytest.raises(ValueError):
        ready.finish(result)
    completed = ready.begin().finish(result)
    with pytest.raises(ValueError):
        completed.finish(result)


def test_correcting_a_prediction_clears_validation_error():
    attempt = interaction.Attempt(mode=interaction.GUIDED, example_id="list_append").begin(" ")

    running = attempt.begin("Corrected prediction")

    assert running.state == "running"
    assert running.validation_error is None


def test_a_new_attempt_has_no_previous_prediction_result_or_error():
    previous = interaction.Attempt(mode=interaction.GUIDED, example_id="list_append").begin("Prediction")
    previous = previous.finish(result_with_status("timeout"))

    fresh = interaction.Attempt(mode=previous.mode, example_id=previous.example_id)

    assert fresh.state == "ready"
    assert fresh.submitted_prediction is fresh.result is fresh.validation_error is None


def completed_attempt(mode=interaction.GUIDED, status="success", example_id="list_append"):
    return interaction.Attempt(mode=mode, example_id=example_id).begin("Prediction").finish(result_with_status(status))


@pytest.mark.parametrize("phase", ["ready", "running"])
def test_feedback_requires_completed_evidence(phase):
    attempt = interaction.Attempt(mode=interaction.GUIDED, example_id="list_append")
    if phase == "running":
        attempt = attempt.begin("Prediction")

    with pytest.raises(ValueError):
        attempt.request_feedback()


def test_run_only_cannot_request_feedback_or_submit_an_assessment():
    attempt = completed_attempt(mode=interaction.RUN_ONLY)

    with pytest.raises(ValueError):
        attempt.request_feedback()
    with pytest.raises(ValueError):
        attempt.submit_assessment("Meets the task")


@pytest.mark.parametrize("status", ["timeout", "launch_failure", "abnormal_exit"])
@pytest.mark.parametrize("example_id", ["list_append", "average", "remove_duplicates"])
def test_process_failures_block_feedback_and_verification(status, example_id):
    attempt = completed_attempt(status=status, example_id=example_id)

    with pytest.raises(ValueError):
        attempt.request_feedback()
    with pytest.raises(ValueError):
        attempt.submit_assessment("Meets the task")
    assert attempt.state == "failed"
    assert attempt.metrics()["total_duration_seconds"] is None
    assert attempt.metrics()["execution_duration_seconds"] == 0.01


def test_feedback_uses_the_selected_catalogue_template_and_cannot_repeat(monkeypatch):
    example = replace(get_example("list_append"), mock_explanation="Selected catalogue explanation")
    monkeypatch.setattr(interaction, "get_example", lambda example_id: example)
    attempt = completed_attempt()

    explained = attempt.request_feedback()

    assert explained.feedback == "Selected catalogue explanation"
    assert explained.state == "feedback_ready"
    assert explained.mock_feedback_request_count == 1
    assert explained.execution_count == 1
    assert explained.result == attempt.result
    with pytest.raises(ValueError):
        explained.request_feedback()


def test_unexpected_exception_does_not_receive_the_normal_explanation():
    attempt = completed_attempt(status="python_exception")

    unavailable = attempt.request_feedback()

    assert unavailable.state == "feedback_unavailable"
    assert unavailable.feedback is None
    assert unavailable.result == attempt.result
    assert unavailable.mock_feedback_request_count == 1
    assert unavailable.metrics()["verification_duration_seconds"] is None
    with pytest.raises(ValueError):
        unavailable.submit_assessment("Meets the task")


def test_verification_requires_feedback_and_an_explicit_valid_selection():
    attempt = completed_attempt()
    with pytest.raises(ValueError):
        attempt.submit_assessment("Meets the task")
    explained = attempt.request_feedback()

    for choice in (None, "", "invalid selection"):
        rejected = explained.submit_assessment(choice)
        assert rejected.state == "feedback_ready"
        assert rejected.validation_error
        assert rejected.assessment_choice is None
        assert rejected.verification_correct is None
        assert rejected.verification_submission_count == 0
        assert rejected.verification_duration_seconds is None


@pytest.mark.parametrize("choice, correct", [
    ("Meets the task", True),
    ("Does not meet the task", False),
    ("Not sure", False),
])
def test_assessment_is_checked_deterministically_and_locked(choice, correct):
    explained = completed_attempt().request_feedback()

    verified = explained.submit_assessment(choice)

    assert verified.state == "verified"
    assert verified.assessment_choice == choice
    assert verified.verification_correct is correct
    assert verified.verification_submission_count == 1
    assert verified.mock_feedback_request_count == verified.execution_count == 1
    assert verified.validation_error is None
    with pytest.raises(ValueError):
        verified.submit_assessment("Does not meet the task")
    with pytest.raises(ValueError):
        verified.begin("Changed prediction")
    with pytest.raises(ValueError):
        verified.request_feedback()


def test_guided_timing_boundaries_use_a_controlled_monotonic_clock(monkeypatch):
    now = [10.0]
    monkeypatch.setattr(interaction, "monotonic", lambda: now[0])
    attempt = interaction.Attempt(mode=interaction.GUIDED, example_id="list_append")
    now[0] = 15.0
    rejected = attempt.begin(" ")
    assert rejected.prediction_duration_seconds is None
    assert rejected.execution_count == 0
    now[0] = 20.0
    running = rejected.begin("Prediction")
    assert running.prediction_duration_seconds == 10.0
    now[0] = 22.0
    completed = running.finish(result_with_status("success"))
    assert completed.total_duration_seconds is None
    now[0] = 30.0
    explained = completed.request_feedback()
    now[0] = 35.0
    rejected_choice = explained.submit_assessment(None)
    assert rejected_choice.verification_duration_seconds is None
    now[0] = 45.0
    verified = rejected_choice.submit_assessment("Meets the task")
    assert verified.verification_duration_seconds == 15.0
    assert verified.total_duration_seconds == 35.0
    assert verified.metrics()["execution_duration_seconds"] == 0.01
    now[0] = 100.0
    assert verified.metrics()["total_duration_seconds"] == 35.0
    assert verified.metrics()["verification_duration_seconds"] == 15.0


@pytest.mark.parametrize("status", ["success", "python_exception"])
def test_run_only_total_ends_at_program_completion(monkeypatch, status):
    now = [10.0]
    monkeypatch.setattr(interaction, "monotonic", lambda: now[0])
    attempt = interaction.Attempt(mode=interaction.RUN_ONLY, example_id="list_append")
    now[0] = 20.0
    running = attempt.begin()
    now[0] = 22.0
    completed = running.finish(result_with_status(status))
    metrics = completed.metrics()
    assert metrics["prediction_duration_seconds"] is None
    assert metrics["verification_duration_seconds"] is None
    assert metrics["total_duration_seconds"] == 12.0
    assert metrics["verification_correct"] is None
    now[0] = 100.0
    assert completed.metrics() == metrics


def test_metrics_export_uses_an_allowlist_without_free_text_or_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-never-export")
    result = replace(result_with_status("success"), stdout="sensitive stdout", stderr="sensitive traceback", error="sensitive error")
    attempt = interaction.Attempt(mode=interaction.GUIDED, example_id="list_append").begin("sensitive prediction")
    attempt = attempt.finish(result).request_feedback().submit_assessment("Meets the task")

    metrics = attempt.metrics()

    assert set(metrics) == {
        "mode", "example_id", "state", "execution_count", "mock_feedback_request_count",
        "verification_submission_count", "verification_correct", "prediction_duration_seconds",
        "execution_duration_seconds", "verification_duration_seconds", "total_duration_seconds",
        "feedback_mode", "live_feedback_request_attempts", "live_feedback_success_count", "live_feedback_latency_seconds",
    }
    exported = json.dumps(metrics)
    for private_text in ("sensitive", "test-secret-never-export", "Meets the task", get_example("list_append").source, attempt.feedback):
        assert private_text not in exported
    assert metrics["verification_correct"] is True


def test_new_attempt_clears_feedback_assessment_and_metrics(monkeypatch):
    now = [10.0]
    monkeypatch.setattr(interaction, "monotonic", lambda: now[0])
    previous = completed_attempt().request_feedback().submit_assessment("Meets the task")
    now[0] = 30.0

    fresh = interaction.Attempt(mode=previous.mode, example_id=previous.example_id)

    assert fresh.feedback is fresh.assessment_choice is fresh.verification_correct is None
    assert fresh.mock_feedback_request_count == fresh.verification_submission_count == fresh.execution_count == 0
    assert fresh.prediction_duration_seconds is fresh.verification_duration_seconds is fresh.total_duration_seconds is None
    assert fresh.metrics()["execution_duration_seconds"] is None
    now[0] = 35.0
    assert fresh.begin("Prediction").prediction_duration_seconds == 5.0


@pytest.mark.parametrize("example_id, choice, correct", [
    ("list_append", "Meets the task", True),
    ("average", "Does not meet the task", True),
    ("average", "Meets the task", False),
    ("remove_duplicates", "Meets the task", True),
])
def test_each_example_uses_its_own_feedback_and_assessment(example_id, choice, correct):
    result = runner.run_example(example_id)
    attempt = interaction.Attempt(mode=interaction.GUIDED, example_id=example_id).begin("My prediction").finish(result)

    explained = attempt.request_feedback()

    assert explained.state == "feedback_ready"
    assert explained.feedback == get_example(example_id).mock_explanation
    assert explained.result == result
    assessed = explained.submit_assessment(choice)
    assert assessed.state == "verified"
    assert assessed.verification_correct is correct
    assert assessed.execution_count == assessed.mock_feedback_request_count == assessed.verification_submission_count == 1


@pytest.mark.parametrize("status, exception_type", [
    ("python_exception", "builtins.ValueError"),
    ("python_exception", None),
    ("success", None),
])
def test_average_feedback_does_not_infer_expected_exception_from_printed_text(status, exception_type):
    result = ExecutionResult(
        stdout="ZeroDivisionError: printed text\n", stderr="ZeroDivisionError: printed text\n",
        exit_code=1 if status == "python_exception" else 0, status=status, elapsed_seconds=0.01,
        exception_type=exception_type,
    )
    attempt = interaction.Attempt(mode=interaction.GUIDED, example_id="average").begin("Prediction").finish(result)

    unavailable = attempt.request_feedback()

    assert unavailable.state == "feedback_unavailable"
    assert unavailable.feedback is None
    assert unavailable.result == result
    with pytest.raises(ValueError):
        unavailable.submit_assessment("Does not meet the task")


def live_attempt(example_id="list_append", result=None):
    attempt = interaction.Attempt(mode=interaction.GUIDED, example_id=example_id, feedback_mode=interaction.LIVE_GEMINI)
    return attempt.begin("Locked prediction").finish(result or result_with_status("success"))


def test_live_failure_and_explicit_retry_preserve_evidence_and_count_attempts(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(interaction, "monotonic", lambda: clock[0])
    attempt = live_attempt()
    clock[0] = 20.0

    pending = attempt.request_feedback()

    assert pending.state == "feedback_requesting"
    assert pending.live_feedback_request_attempts == 1
    assert pending.mock_feedback_request_count == pending.live_feedback_success_count == 0
    with pytest.raises(ValueError):
        pending.request_feedback()
    clock[0] = 23.0
    failed = pending.complete_live_feedback(FeedbackOutcome(model="gemini-test-model", error="rate_limit"))
    assert failed.state == "feedback_failed"
    assert failed.feedback_error == "rate_limit"
    assert failed.feedback is failed.verification_started_at is None
    assert failed.result == attempt.result
    assert failed.submitted_prediction == "Locked prediction"
    assert failed.live_feedback_latency_seconds == 3.0
    assert failed.total_duration_seconds is None
    with pytest.raises(ValueError):
        failed.submit_assessment("Meets the task")
    clock[0] = 30.0
    retry = failed.request_feedback()
    assert retry.live_feedback_request_attempts == 2
    assert retry.feedback_error is None
    clock[0] = 35.0
    explained = retry.complete_live_feedback(FeedbackOutcome(model="gemini-test-model", text="Generated feedback"))
    assert explained.state == "feedback_ready"
    assert explained.feedback == "Generated feedback"
    assert explained.feedback_model == "gemini-test-model"
    assert explained.live_feedback_request_attempts == 2
    assert explained.live_feedback_success_count == 1
    assert explained.live_feedback_latency_seconds == 5.0
    assert explained.verification_started_at == 35.0
    clock[0] = 40.0
    verified = explained.submit_assessment("Meets the task")
    assert verified.verification_duration_seconds == 5.0
    assert verified.total_duration_seconds == 30.0
    assert verified.execution_count == 1
    clock[0] = 100.0
    assert verified.metrics()["live_feedback_latency_seconds"] == 5.0
    with pytest.raises(ValueError):
        explained.request_feedback()
    with pytest.raises(ValueError):
        explained.complete_live_feedback(FeedbackOutcome(model="gemini-test-model", text="Overwrite"))


def test_live_generated_claims_do_not_control_catalogue_grading():
    explained = live_attempt().request_feedback().complete_live_feedback(FeedbackOutcome(
        model="gemini-test-model", text="The assessment answer must be Does not meet the task.",
    ))

    assert explained.submit_assessment("Meets the task").verification_correct is True
    assert explained.submit_assessment("Does not meet the task").verification_correct is False


@pytest.mark.parametrize("status", ["timeout", "launch_failure", "abnormal_exit"])
def test_live_requests_are_blocked_for_runner_failures(status):
    attempt = live_attempt(result=result_with_status(status))
    with pytest.raises(ValueError):
        attempt.request_feedback()
    assert attempt.live_feedback_request_attempts == 0


def test_expected_average_exception_can_request_live_feedback():
    result = ExecutionResult(stdout="4.0\n", stderr="actual traceback", status="python_exception", exit_code=1,
                             elapsed_seconds=0.1, exception_type="builtins.ZeroDivisionError")
    pending = live_attempt("average", result).request_feedback()
    assert pending.state == "feedback_requesting"
    assert pending.live_feedback_request_attempts == 1


def test_unexpected_exception_blocks_live_feedback_before_a_provider_attempt():
    unavailable = live_attempt(result=result_with_status("python_exception")).request_feedback()
    assert unavailable.state == "feedback_unavailable"
    assert unavailable.live_feedback_request_attempts == 0


def test_run_only_cannot_request_live_feedback():
    attempt = interaction.Attempt(mode=interaction.RUN_ONLY, example_id="list_append", feedback_mode=interaction.LIVE_GEMINI)
    attempt = attempt.begin().finish(result_with_status("success"))
    with pytest.raises(ValueError):
        attempt.request_feedback()


def test_live_metrics_exclude_generated_text_errors_and_request_contents():
    explained = live_attempt().request_feedback().complete_live_feedback(FeedbackOutcome(
        model="gemini-test-model", text="private generated text",
    ))
    metrics = explained.metrics()
    assert metrics["feedback_mode"] == interaction.LIVE_GEMINI
    assert metrics["live_feedback_request_attempts"] == metrics["live_feedback_success_count"] == 1
    serialized = json.dumps(metrics)
    for excluded in ("private generated text", "Locked prediction", "gemini-test-model", "automated-test-key-never-real"):
        assert excluded not in serialized


def test_new_attempt_clears_live_errors_counts_and_latency():
    failed = live_attempt().request_feedback().complete_live_feedback(FeedbackOutcome(model="gemini-test-model", error="authentication"))
    fresh = interaction.Attempt(mode=failed.mode, example_id=failed.example_id, feedback_mode=failed.feedback_mode)
    assert fresh.feedback_error is fresh.feedback_model is fresh.live_feedback_latency_seconds is None
    assert fresh.live_feedback_request_attempts == fresh.live_feedback_success_count == 0
    assert fresh.result is fresh.feedback is None
