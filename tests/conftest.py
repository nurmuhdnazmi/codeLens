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
