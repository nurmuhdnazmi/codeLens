from dataclasses import dataclass, replace
from typing import Literal

from codelens.runner import ExecutionResult


RUN_ONLY = "Run-only"
GUIDED = "Predict–Explain–Verify"
MODES = (RUN_ONLY, GUIDED)
MAX_PREDICTION_LENGTH = 2000


@dataclass(frozen=True, slots=True)
class Attempt:
    mode: Literal["Run-only", "Predict–Explain–Verify"]
    example_id: str
    submitted_prediction: str | None = None
    result: ExecutionResult | None = None
    state: Literal["ready", "running", "completed", "failed"] = "ready"
    validation_error: str | None = None

    def begin(self, prediction: str = "") -> "Attempt":
        if self.state != "ready":
            raise ValueError("Start a new attempt before running again.")

        if self.mode == GUIDED:
            if not prediction.strip():
                return replace(self, validation_error="Predict all four printed lines before running.")
            if len(prediction) > MAX_PREDICTION_LENGTH:
                return replace(self, validation_error="Keep your prediction within 2,000 characters.")

        return replace(
            self, state="running", validation_error=None,
            submitted_prediction=prediction if self.mode == GUIDED else None,
        )

    def finish(self, result: ExecutionResult) -> "Attempt":
        if self.state != "running":
            raise ValueError("Only a running attempt can accept a result.")
        state = "completed" if result.status in ("success", "python_exception") else "failed"
        return replace(self, state=state, result=result)
