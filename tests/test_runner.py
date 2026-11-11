from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from codelens import runner
from codelens.catalogue import get_example


EXPECTED_STDOUT = "[1]\n[1, 2]\n[3]\n[1, 2, 4]\n"


def use_test_source(monkeypatch, source):
    """Replace only the test lookup, without adding production examples."""
    def lookup(example_id):
        return replace(get_example(example_id), source=source)

    monkeypatch.setattr(runner, "get_example", lookup)


def test_approved_example_returns_actual_evidence():
    result = runner.run_example("list_append")

    assert result.status == "success"
    assert result.stdout == EXPECTED_STDOUT
    assert result.stderr == ""
    assert result.exit_code == 0
    assert result.elapsed_seconds > 0
    assert result.error is None


def test_separate_runs_start_with_fresh_function_defaults():
    first = runner.run_example("list_append")
    second = runner.run_example("list_append")

    assert first.stdout == second.stdout == EXPECTED_STDOUT
    assert first.status == second.status == "success"


@pytest.mark.parametrize("example_id", ["unknown", "", "print('injected')"])
def test_unapproved_ids_are_rejected_before_process_creation(monkeypatch, example_id):
    launch = Mock()
    monkeypatch.setattr(runner.subprocess, "run", launch)

    with pytest.raises(KeyError):
        runner.run_example(example_id)

    launch.assert_not_called()


def test_process_uses_the_execution_boundaries_and_cleans_up(monkeypatch):
    real_run = subprocess.run
    working_directories = []

    def inspect_launch(command, **options):
        assert command[0] == sys.executable
        assert "-I" in command
        assert options["shell"] is False
        assert options["stdin"] == subprocess.DEVNULL
        assert options["timeout"] == 2
        assert options["env"] == {}
        assert options["capture_output"] is True
        working_directory = Path(options["cwd"])
        assert working_directory != Path.cwd()
        assert (working_directory / "example.py").read_text() == get_example("list_append").source
        working_directories.append(working_directory)
        return real_run(command, **options)

    monkeypatch.setattr(runner.subprocess, "run", inspect_launch)

    first = runner.run_example("list_append")
    second = runner.run_example("list_append")

    assert first.stdout == second.stdout == EXPECTED_STDOUT
    assert len(working_directories) == 2
    assert working_directories[0] != working_directories[1]
    assert all(not directory.exists() for directory in working_directories)


def test_real_child_has_no_application_secrets_and_closed_stdin(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-do-not-inherit")
    monkeypatch.setenv("CODELENS_SECRET", "test-secret-do-not-inherit")
    use_test_source(monkeypatch, (
        "import json, os, sys\n"
        "print(json.dumps({\n"
        "    'api_key': os.getenv('OPENAI_API_KEY'),\n"
        "    'secret': os.getenv('CODELENS_SECRET'),\n"
        "    'isolated': sys.flags.isolated,\n"
        "    'stdin': sys.stdin.read(),\n"
        "}))\n"
    ))

    result = runner.run_example("list_append")

    assert result.status == "success"
    assert json.loads(result.stdout) == {
        "api_key": None, "secret": None, "isolated": 1, "stdin": "",
    }


@pytest.mark.parametrize("source, exception_name", [
    ("print('before failure')\nraise ValueError('test failure')\n", "ValueError"),
    ("1 / 0\n", "ZeroDivisionError"),
    ("if True print('invalid syntax')\n", "SyntaxError"),
])
def test_real_python_exceptions_are_recognised(monkeypatch, source, exception_name):
    use_test_source(monkeypatch, source)

    result = runner.run_example("list_append")

    assert result.status == "python_exception"
    assert result.exit_code == 1
    assert "Traceback" in result.stderr
    assert exception_name in result.stderr
    assert result.stdout == ("before failure\n" if exception_name == "ValueError" else "")
    assert result.elapsed_seconds > 0


@pytest.mark.parametrize("source, exit_code", [
    ("raise SystemExit(7)\n", 7),
    ("raise KeyboardInterrupt\n", -2),
    ("import sys\nsys.stderr.write('ValueError: fake traceback\\n')\nsys.exit(1)\n", 1),
])
def test_real_uncaught_exits_are_not_classified_from_stderr(monkeypatch, source, exit_code):
    use_test_source(monkeypatch, source)

    result = runner.run_example("list_append")

    assert result.status == "abnormal_exit"
    # KeyboardInterrupt uses a platform-dependent return code.
    if exit_code == -2:
        assert result.exit_code != 0
    else:
        assert result.exit_code == exit_code


@pytest.mark.parametrize("partial_stdout, partial_stderr, stdout, stderr", [
    (b"partial output\n", b"partial error\n", "partial output\n", "partial error\n"),
    (None, None, "", ""),
    ("text output", "text error", "text output", "text error"),
])
def test_timeout_preserves_partial_evidence(monkeypatch, partial_stdout, partial_stderr, stdout, stderr):
    launch = Mock(side_effect=subprocess.TimeoutExpired(
        cmd=[sys.executable], timeout=2, output=partial_stdout, stderr=partial_stderr,
    ))
    monkeypatch.setattr(runner.subprocess, "run", launch)

    result = runner.run_example("list_append")

    assert result.status == "timeout"
    assert result.stdout == stdout
    assert result.stderr == stderr
    assert result.exit_code is None
    assert result.elapsed_seconds >= 0


def test_launch_failure_is_not_program_exception_evidence(monkeypatch):
    monkeypatch.setattr(runner.subprocess, "run", Mock(side_effect=FileNotFoundError("Python unavailable")))

    result = runner.run_example("list_append")

    assert result.status == "launch_failure"
    assert result.stdout == result.stderr == ""
    assert result.exit_code is None
    assert "Python unavailable" in result.error
    assert result.elapsed_seconds >= 0


def test_real_timeout_returns_partial_output(monkeypatch):
    use_test_source(monkeypatch, "import time\nprint('started', flush=True)\ntime.sleep(10)\n")

    result = runner.run_example("list_append")

    assert result.status == "timeout"
    assert result.stdout == "started\n"
    assert result.exit_code is None
    assert result.elapsed_seconds >= 2


def test_signal_exit_is_distinct_and_preserves_output(monkeypatch):
    completed = subprocess.CompletedProcess(args=[sys.executable], returncode=-9, stdout="before\n", stderr="")
    monkeypatch.setattr(runner.subprocess, "run", Mock(return_value=completed))

    result = runner.run_example("list_append")

    assert result.status == "abnormal_exit"
    assert result.exit_code == -9
    assert result.stdout == "before\n"


@pytest.mark.parametrize("timeout", [False, True])
def test_cleanup_failure_preserves_execution_evidence(monkeypatch, timeout):
    real_cleanup = runner.TemporaryDirectory.cleanup

    def cleanup_then_fail(directory):
        real_cleanup(directory)
        raise OSError("test cleanup failure")

    monkeypatch.setattr(runner.TemporaryDirectory, "cleanup", cleanup_then_fail)
    if timeout:
        monkeypatch.setattr(runner.subprocess, "run", Mock(side_effect=subprocess.TimeoutExpired(
            cmd=[sys.executable], timeout=2, output=b"partial\n", stderr=b"partial error\n",
        )))

    result = runner.run_example("list_append")

    assert result.status == ("timeout" if timeout else "success")
    assert result.stdout == ("partial\n" if timeout else EXPECTED_STDOUT)
    assert result.stderr == ("partial error\n" if timeout else "")
    assert result.exit_code == (None if timeout else 0)
    assert "cleanup" in result.error
