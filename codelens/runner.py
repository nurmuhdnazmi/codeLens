from dataclasses import dataclass, replace
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Literal

from codelens.catalogue import get_example


RunStatus = Literal["success", "python_exception", "timeout", "launch_failure", "abnormal_exit"]


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int | None
    status: RunStatus
    elapsed_seconds: float
    error: str | None = None
    exception_type: str | None = None


# Only this wrapper's caught Exceptions are recognised as program exceptions.
_CHILD_RUNNER = """\
from pathlib import Path
import runpy
import sys
import traceback

try:
    runpy.run_path("example.py", run_name="__main__")
except Exception as exc:
    traceback.print_exc()
    Path("python_exception").write_text(
        f"{type(exc).__module__}.{type(exc).__qualname__}", encoding="utf-8"
    )
    sys.exit(1)
"""


def _text(output: str | bytes | None) -> str:
    # TimeoutExpired can contain bytes even when text=True.
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output or ""


def run_example(example_id: str) -> ExecutionResult:
    """Execute catalogue source only. Unknown IDs raise KeyError before launch."""
    example = get_example(example_id)
    started = perf_counter()
    result = None

    try:
        with TemporaryDirectory(prefix="codelens-") as directory:
            working_directory = Path(directory)
            (working_directory / "example.py").write_text(example.source, encoding="utf-8")
            try:
                completed = subprocess.run(
                    [sys.executable, "-I", "-X", "utf8", "-c", _CHILD_RUNNER],
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    cwd=working_directory,
                    env={},
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=2,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                result = ExecutionResult(
                    stdout=_text(exc.stdout), stderr=_text(exc.stderr),
                    exit_code=None, status="timeout",
                    elapsed_seconds=perf_counter() - started,
                )
                return result

            elapsed = perf_counter() - started
            exception_type = None
            metadata_error = None
            if completed.returncode == 0:
                status: RunStatus = "success"
            elif completed.returncode == 1 and (working_directory / "python_exception").is_file():
                try:
                    exception_type = (working_directory / "python_exception").read_text(encoding="utf-8")
                    status = "python_exception"
                except (OSError, UnicodeError) as exc:
                    status = "abnormal_exit"
                    metadata_error = f"Could not read exception metadata: {exc}"
            else:
                status = "abnormal_exit"

            result = ExecutionResult(
                stdout=completed.stdout, stderr=completed.stderr,
                exit_code=completed.returncode, status=status,
                elapsed_seconds=elapsed,
                exception_type=exception_type, error=metadata_error,
            )
            return result
    except OSError as exc:
        if result is not None:
            return replace(result, error=f"Temporary directory cleanup failed: {exc}")
        return ExecutionResult(
            stdout="", stderr="", exit_code=None, status="launch_failure",
            elapsed_seconds=perf_counter() - started,
            error=f"Could not prepare or launch Python: {exc}",
        )
