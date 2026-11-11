from dataclasses import FrozenInstanceError

import pytest

from codelens import interaction
from codelens.runner import ExecutionResult


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
