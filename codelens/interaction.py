from dataclasses import dataclass, field, replace
from time import monotonic
from typing import Final, Literal

from codelens.runner import ExecutionResult
from codelens.catalogue import get_example
from codelens.live_feedback import FeedbackError, FeedbackOutcome


RUN_ONLY = "Run-only"
GUIDED = "Predict–Explain–Verify"
MODES = (RUN_ONLY, GUIDED)
MAX_PREDICTION_LENGTH = 2000
MOCK: Final = "Mock"
LIVE_GEMINI: Final = "Live Gemini"
FEEDBACK_MODES = (MOCK, LIVE_GEMINI)


@dataclass(frozen=True, slots=True)
class Attempt:
    mode: Literal["Run-only", "Predict–Explain–Verify"]
    example_id: str
    submitted_prediction: str | None = None
    result: ExecutionResult | None = None
    state: Literal[
        "ready", "running", "completed", "failed", "feedback_ready", "feedback_unavailable", "verified",
        "feedback_requesting", "feedback_failed",
    ] = "ready"
    validation_error: str | None = None
    feedback: str | None = None
    assessment_choice: str | None = None
    verification_correct: bool | None = None
    execution_count: int = 0
    mock_feedback_request_count: int = 0
    verification_submission_count: int = 0
    created_at: float = field(default_factory=lambda: monotonic(), repr=False)
    verification_started_at: float | None = field(default=None, repr=False)
    prediction_duration_seconds: float | None = None
    verification_duration_seconds: float | None = None
    total_duration_seconds: float | None = None
    feedback_mode: Literal["Mock", "Live Gemini"] = MOCK
    feedback_error: FeedbackError | None = None
    feedback_model: str | None = None
    live_feedback_request_attempts: int = 0
    live_feedback_success_count: int = 0
    live_feedback_latency_seconds: float | None = None
    live_feedback_started_at: float | None = field(default=None, repr=False)

    def begin(self, prediction: str = "") -> "Attempt":
        if self.state != "ready":
            raise ValueError("Start a new attempt before running again.")

        if self.mode == GUIDED:
            if not prediction.strip():
                return replace(self, validation_error=f"{get_example(self.example_id).prediction_prompt} before running.")
            if len(prediction) > MAX_PREDICTION_LENGTH:
                return replace(self, validation_error="Keep your prediction within 2,000 characters.")

        return replace(
            self, state="running", validation_error=None,
            submitted_prediction=prediction if self.mode == GUIDED else None,
            execution_count=self.execution_count + 1,
            prediction_duration_seconds=monotonic() - self.created_at if self.mode == GUIDED else None,
        )

    def finish(self, result: ExecutionResult) -> "Attempt":
        if self.state != "running":
            raise ValueError("Only a running attempt can accept a result.")
        state: Literal["completed", "failed"] = "completed" if result.status in ("success", "python_exception") else "failed"
        total = monotonic() - self.created_at if state == "completed" and self.mode == RUN_ONLY else None
        return replace(self, state=state, result=result, total_duration_seconds=total)

    def request_feedback(self) -> "Attempt":
        if (
            self.mode != GUIDED or self.result is None or self.feedback_mode not in FEEDBACK_MODES
            or not (self.state == "completed" or (self.feedback_mode == LIVE_GEMINI and self.state == "feedback_failed"))
            or self.result.status not in ("success", "python_exception")
        ):
            raise ValueError("Feedback requires guided mode and completed program evidence.")
        example = get_example(self.example_id)
        expected_exception = example.expected_exception_type
        matches = (
            self.result.status == "success" and expected_exception is None
        ) or (
            self.result.status == "python_exception" and expected_exception is not None
            and self.result.exception_type == expected_exception
        )
        if not matches:
            return replace(self, state="feedback_unavailable", mock_feedback_request_count=1 if self.feedback_mode == MOCK else 0)
        if self.feedback_mode == LIVE_GEMINI:
            return replace(
                self, state="feedback_requesting", feedback_error=None,
                live_feedback_request_attempts=self.live_feedback_request_attempts + 1,
                live_feedback_started_at=monotonic(),
            )
        return replace(
            self, state="feedback_ready", feedback=example.mock_explanation,
            mock_feedback_request_count=1, verification_started_at=monotonic(),
        )

    def complete_live_feedback(self, outcome: FeedbackOutcome) -> "Attempt":
        if self.feedback_mode != LIVE_GEMINI or self.state != "feedback_requesting" or self.live_feedback_started_at is None:
            raise ValueError("Only a pending live request can accept a response.")
        now = monotonic()
        error = outcome.error or ("empty" if not outcome.text or not outcome.text.strip() else None)
        if error:
            return replace(
                self, state="feedback_failed", feedback_error=error, feedback_model=outcome.model,
                live_feedback_latency_seconds=now - self.live_feedback_started_at,
            )
        return replace(
            self, state="feedback_ready", feedback=outcome.text, feedback_model=outcome.model,
            feedback_error=None, live_feedback_success_count=self.live_feedback_success_count + 1,
            live_feedback_latency_seconds=now - self.live_feedback_started_at,
            verification_started_at=now,
        )

    def submit_assessment(self, choice: str | None) -> "Attempt":
        if (
            self.mode != GUIDED or self.state != "feedback_ready" or self.feedback is None
            or self.verification_started_at is None
        ):
            raise ValueError("An assessment requires available feedback and cannot be submitted twice.")
        question = get_example(self.example_id).verification
        if choice not in question.choices:
            return replace(self, validation_error="Select an assessment before submitting.")
        now = monotonic()
        return replace(
            self, state="verified", assessment_choice=choice,
            verification_correct=choice == question.answer,
            verification_submission_count=1, validation_error=None,
            verification_duration_seconds=now - self.verification_started_at,
            total_duration_seconds=now - self.created_at,
        )

    def metrics(self) -> dict[str, str | int | float | bool | None]:
        # Keep export fields explicit so free text and execution evidence cannot leak.
        return {
            "mode": self.mode,
            "example_id": self.example_id,
            "state": self.state,
            "execution_count": self.execution_count,
            "mock_feedback_request_count": self.mock_feedback_request_count,
            "verification_submission_count": self.verification_submission_count,
            "verification_correct": self.verification_correct,
            "prediction_duration_seconds": self.prediction_duration_seconds,
            "execution_duration_seconds": self.result.elapsed_seconds if self.result is not None else None,
            "verification_duration_seconds": self.verification_duration_seconds,
            "total_duration_seconds": self.total_duration_seconds,
            "feedback_mode": self.feedback_mode,
            "live_feedback_request_attempts": self.live_feedback_request_attempts,
            "live_feedback_success_count": self.live_feedback_success_count,
            "live_feedback_latency_seconds": self.live_feedback_latency_seconds,
        }
