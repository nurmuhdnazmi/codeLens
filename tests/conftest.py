import pytest

from codelens import live_feedback


class UnexpectedGeminiRequest(BaseException):
    pass


@pytest.fixture(autouse=True)
def block_real_gemini_requests(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "automated-test-key-never-real")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    def forbidden_client(*args, **kwargs):
        raise UnexpectedGeminiRequest("Automated tests must replace the Gemini client.")

    monkeypatch.setattr(live_feedback.genai, "Client", forbidden_client)


def pytest_addoption(parser):
    parser.addoption("--run-e2e", action="store_true", help="Run the real-browser CodeLens tests.")
    parser.addoption("--e2e-artifacts", default="output/playwright/e2e", help="Parent directory for browser-test evidence.")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-e2e"):
        skip = pytest.mark.skip(reason="Use --run-e2e and install the e2e extra to run browser tests.")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip)
