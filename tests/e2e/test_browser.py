"""End-to-end checks against an unmodified app and real approved subprocesses."""

import ast
import re
import json
from urllib.parse import urlsplit

import pytest


pytestmark = pytest.mark.e2e
GUIDED = "Predict–Explain–Verify"
EXAMPLES = [
    ("list_append", "List append", "Meets the task"),
    ("average", "Average", "Does not meet the task"),
    ("remove_duplicates", "Remove duplicates", "Meets the task"),
]
METRIC_FIELDS = {
    "mode", "example_id", "state", "execution_count", "mock_feedback_request_count",
    "verification_submission_count", "verification_correct", "prediction_duration_seconds",
    "execution_duration_seconds", "verification_duration_seconds", "total_duration_seconds",
    "feedback_mode", "live_feedback_request_attempts", "live_feedback_success_count",
    "live_feedback_latency_seconds",
}


def check_metrics(metrics):
    assert set(metrics) == METRIC_FIELDS
    assert metrics["live_feedback_request_attempts"] == metrics["live_feedback_success_count"] == 0
    assert metrics["live_feedback_latency_seconds"] is None


def check_fresh(app, expect, example_id="list_append", mode=GUIDED):
    app.state("ready")
    expect(app.section("execution_evidence")).to_have_count(0)
    expect(app.section("feedback")).to_have_count(0)
    expect(app.section("fix_assessment")).to_have_count(0)
    expect(app.page.get_by_role("button", name="Run approved example", exact=True)).to_be_enabled()
    expect(app.page.get_by_text("Select an assessment before submitting.", exact=True)).to_have_count(0)
    if mode == GUIDED:
        expect(app.page.get_by_role("textbox")).to_have_value("")
    else:
        expect(app.page.get_by_role("textbox")).to_have_count(0)
    metrics = app.metrics("ready", example_id)
    assert metrics["mode"] == mode
    assert metrics["execution_count"] == metrics["mock_feedback_request_count"] == metrics["verification_submission_count"] == 0
    for name in ("verification_correct", "prediction_duration_seconds", "execution_duration_seconds", "verification_duration_seconds", "total_duration_seconds", "live_feedback_latency_seconds"):
        assert metrics[name] is None
    check_metrics(metrics)


def check_evidence(app, expect, example_id, guided=False):
    evidence = app.section("execution_evidence")
    codes = evidence.locator("code")
    stdout = codes.nth(1 if guided else 0).inner_text().strip()
    if example_id == "list_append":
        assert stdout == "[1]\n[1, 2]\n[3]\n[1, 2, 4]"
    elif example_id == "average":
        assert stdout == "4.0"
        expect(evidence).to_contain_text("Status: python_exception")
        expect(evidence).to_contain_text("Exit code: 1")
        traceback = codes.last.inner_text()
        assert "Traceback (most recent call last):" in traceback
        assert traceback.rstrip().endswith("ZeroDivisionError: division by zero")
        assert codes.count() == (3 if guided else 2)
    else:
        lines = stdout.splitlines()
        assert len(lines) == 4
        # A set has no promised iteration order. Check membership, uniqueness,
        # unchanged input and the other calls, without fixing the first order.
        first = ast.literal_eval(lines[0])
        assert isinstance(first, list) and len(first) == 3 and set(first) == {1, 2, 3}
        assert lines[1:] == ["[3, 1, 3, 2]", "[]", "[5]"]
    if example_id != "average":
        expect(evidence).to_contain_text("Status: success")
        expect(evidence).to_contain_text("Exit code: 0")
        expect(evidence).to_contain_text("No stderr.")
    return stdout


@pytest.mark.parametrize("example_id,title,answer", EXAMPLES, ids=[item[0] for item in EXAMPLES])
@pytest.mark.parametrize("mode", ["Run-only", GUIDED], ids=["run-only", "guided"])
def test_complete_example_flow(app, expect, example_id, title, answer, mode):
    app.example(title)
    app.mode(mode)
    initial = app.metrics("ready", example_id)
    assert initial["execution_count"] == 0
    expect(app.section("execution_evidence")).to_have_count(0)
    expect(app.section("fix_assessment")).to_have_count(0)
    if mode == GUIDED:
        app.predict("My prediction is text, including print('never execute this prediction').")
    app.run()
    stdout = check_evidence(app, expect, example_id, mode == GUIDED)
    app.screenshot("execution.png", "execution_evidence")
    expect(app.page.get_by_role("button", name="Run approved example", exact=True)).to_be_disabled()
    metrics = app.metrics("completed", example_id)
    assert metrics["execution_count"] == 1
    assert metrics["execution_duration_seconds"] > 0
    check_metrics(metrics)
    if mode == "Run-only":
        expect(app.section("feedback")).to_have_count(0)
        expect(app.page.get_by_role("button", name="Submit assessment", exact=True)).to_have_count(0)
        assert metrics["total_duration_seconds"] > 0
        assert metrics["prediction_duration_seconds"] is None
        assert metrics == app.metrics("completed", example_id)
        assert stdout == check_evidence(app, expect, example_id)
        return
    expect(app.page.get_by_role("textbox")).to_have_count(0)
    expect(app.section("execution_evidence").locator("code").first).to_contain_text("never execute this prediction")
    assert metrics["mock_feedback_request_count"] == 0
    assert metrics["total_duration_seconds"] is None
    app.explain()
    feedback = app.section("feedback")
    expect(feedback).to_contain_text("predefined explanation; no LLM request")
    expect(feedback).to_contain_text("does not semantically assess free-text predictions")
    if example_id == "average":
        expect(feedback).to_contain_text("The task requires None for an empty list.")
    elif example_id == "remove_duplicates":
        expect(feedback).to_contain_text("does not guarantee first-seen order")
    else:
        expect(feedback).to_contain_text("The default list is created once")
    expect(app.page.get_by_role("button", name="Explain my prediction", exact=True)).to_be_disabled()
    assert app.metrics("feedback_ready", example_id)["verification_correct"] is None
    # Submitting no assessment must not grade or lock the question.
    app.page.get_by_role("button", name="Submit assessment", exact=True).click()
    expect(app.section("fix_assessment")).to_contain_text("Select an assessment before submitting.")
    assert app.metrics("feedback_ready", example_id)["verification_submission_count"] == 0
    app.assess(answer)
    expect(app.section("fix_assessment")).to_contain_text("Correct for this question.")
    expect(app.page.get_by_role("button", name="Submit assessment", exact=True)).to_be_disabled()
    expect(app.section("fix_assessment").get_by_role("radio")).to_have_count(0)
    final = app.metrics("verified", example_id)
    assert final["execution_count"] == final["mock_feedback_request_count"] == final["verification_submission_count"] == 1
    assert final["verification_correct"] is True
    assert final["prediction_duration_seconds"] > 0
    assert final["verification_duration_seconds"] > 0
    assert final["total_duration_seconds"] >= final["prediction_duration_seconds"]
    check_metrics(final)
    assert final == app.metrics("verified", example_id)
    app.screenshot("assessment.png", "fix_assessment")


@pytest.mark.parametrize("action", ["example", "mode", "new_attempt", "feedback_mode"])
def test_every_reset_clears_a_verified_attempt(app, expect, action):
    app.mode(GUIDED)
    app.predict("This entire attempt must be cleared.")
    app.run()
    app.explain()
    app.assess("Meets the task")
    assert app.metrics("verified")["verification_submission_count"] == 1
    if action == "example":
        app.example("Average")
        check_fresh(app, expect, example_id="average")
    elif action == "mode":
        app.mode("Run-only")
        check_fresh(app, expect, mode="Run-only")
        app.mode(GUIDED)
        check_fresh(app, expect)
    elif action == "new_attempt":
        app.reset()
        check_fresh(app, expect)
    else:
        app.feedback_mode("Live Gemini")
        check_fresh(app, expect)
        expect(app.page.get_by_text(re.compile("Live Gemini sends the task"))).to_be_visible()
        assert app.metrics("ready")["feedback_mode"] == "Live Gemini"


@pytest.mark.parametrize("phase", ["draft", "validation_error", "executed", "feedback_ready", "assessment_selected"])
def test_example_change_clears_each_incomplete_phase(app, expect, phase):
    app.mode(GUIDED)
    app.predict("An unsubmitted draft" if phase == "draft" else " ")
    if phase == "validation_error":
        app.page.get_by_role("button", name="Run approved example", exact=True).click()
        expect(app.section("code_review")).to_contain_text("before running.")
    elif phase != "draft":
        app.predict("Saved prediction")
        app.run()
        if phase in ("feedback_ready", "assessment_selected"):
            app.explain()
        if phase == "assessment_selected":
            app.select_assessment("Not sure")
    app.example("Average")
    check_fresh(app, expect, example_id="average")
    expect(app.section("code_review")).not_to_contain_text("before running.")
    expect(app.section("code_review").locator("code")).to_contain_text("def average(values):")


@pytest.mark.parametrize("prediction", ["", " \n\t "], ids=["empty", "whitespace"])
def test_invalid_prediction_does_not_execute(app, expect, prediction):
    app.mode(GUIDED)
    app.predict(prediction)
    app.page.get_by_role("button", name="Run approved example", exact=True).click()
    expect(app.section("code_review")).to_contain_text("before running.")
    app.state("ready")
    expect(app.section("execution_evidence")).to_have_count(0)
    metrics = app.metrics("ready")
    assert metrics["execution_count"] == 0
    assert metrics["prediction_duration_seconds"] is None
    app.predict("A corrected prediction")
    app.run()
    expect(app.section("code_review")).not_to_contain_text("before running.")
    assert app.metrics("completed")["execution_count"] == 1


def test_prediction_length_limit_and_locked_text(app, expect):
    app.mode(GUIDED)
    textbox = app.page.get_by_role("textbox")
    textbox.fill("X" * 2500)
    entered = textbox.input_value()
    # The contract is a 2,000-character submission limit, not a particular
    # HTML attribute or a promise to truncate an oversized paste.
    if len(entered) > 2000:
        app.page.get_by_role("button", name="Run approved example", exact=True).click()
        app.state("ready")
        expect(app.section("code_review")).to_contain_text("2,000 characters")
    assert app.metrics("ready")["execution_count"] == 0
    (app.directory / "length-limit.json").write_text(json.dumps({"paste_length": 2500, "field_length_after_paste": len(entered), "submission_limit": 2000}, indent=2))
    textbox.focus()
    app.screenshot("oversized-paste.png")
    accepted = "X" * 2000
    textbox.fill(accepted)
    expect(textbox).to_have_value(accepted)
    app.run()
    expect(app.page.get_by_role("textbox")).to_have_count(0)
    assert app.section("execution_evidence").locator("code").first.inner_text().strip() == accepted
    assert app.metrics("completed")["execution_count"] == 1


@pytest.mark.parametrize("choice,message", [
    ("Does not meet the task", "Incorrect for this question."),
    ("Not sure", "Not sure recorded."),
])
def test_other_assessments_are_recorded_and_locked(app, expect, choice, message):
    app.mode(GUIDED)
    app.predict("A prediction")
    app.run()
    app.explain()
    app.assess(choice)
    expect(app.section("fix_assessment")).to_contain_text(message)
    metrics = app.metrics("verified")
    assert metrics["verification_correct"] is False
    assert metrics["verification_submission_count"] == 1
    expect(app.page.get_by_role("button", name="Submit assessment", exact=True)).to_be_disabled()


def test_repeat_runs_and_ordinary_ui_reruns(app, expect):
    app.run()
    first = check_evidence(app, expect, "list_append")
    recorded = app.metrics("completed")
    guide = app.expander("How to use CodeLens")
    guide.locator("summary").click()
    guide.locator("summary").click()
    assert app.metrics("completed") == recorded
    app.reset()
    check_fresh(app, expect, mode="Run-only")
    app.run()
    assert check_evidence(app, expect, "list_append") == first
    assert app.metrics("completed")["execution_count"] == 1


def test_live_missing_key_is_local_explicit_and_retryable(app, expect):
    app.mode(GUIDED)
    app.feedback_mode("Live Gemini")
    app.predict("A locked prediction, without personal information")
    app.run()
    before = app.metrics("completed")
    assert before["live_feedback_request_attempts"] == 0
    app.page.get_by_role("button", name="Explain my prediction", exact=True).click()
    app.state("feedback_failed")
    expect(app.section("feedback")).to_contain_text("GEMINI_API_KEY is missing")
    expect(app.section("fix_assessment")).to_have_count(0)
    failed = app.metrics("feedback_failed")
    assert failed["live_feedback_request_attempts"] == 1
    assert failed["live_feedback_success_count"] == failed["mock_feedback_request_count"] == 0
    assert failed == app.metrics("feedback_failed")
    app.page.get_by_role("button", name="Retry Gemini feedback", exact=True).click()
    app.state("feedback_failed")
    retried = app.metrics("feedback_failed", live_feedback_request_attempts=2)
    assert retried["live_feedback_request_attempts"] == 2
    assert retried["execution_count"] == 1
    assert retried["live_feedback_latency_seconds"] >= 0
    expect(app.section("feedback")).to_contain_text("GEMINI_API_KEY is missing")


def test_refresh_and_separate_browser_session_clear_state(app, expect, browser, streamlit_url):
    app.run()
    assert app.metrics("completed")["execution_count"] == 1
    context = browser.new_context()
    try:
        context.route("**/*", lambda route: route.continue_() if urlsplit(route.request.url).hostname in ("127.0.0.1", "localhost") else route.abort())
        page = context.new_page()
        page.goto(streamlit_url)
        expect(page.get_by_text("Attempt state: ready", exact=True)).to_be_visible()
        expect(page.locator(".st-key-execution_evidence")).to_have_count(0)
    finally:
        context.close()
    app.page.reload()
    check_fresh(app, expect, mode="Run-only")


def test_navigation_and_responsive_comparison(app, expect):
    guide = app.expander("How to use CodeLens")
    metrics = app.expander("Current-attempt metrics")
    assert guide.get_attribute("open") is None
    assert metrics.get_attribute("open") is None
    guide.locator("summary").focus()
    app.page.keyboard.press("Enter")
    expect(guide).to_have_attribute("open", "")
    app.page.keyboard.press("Enter")
    expect(guide).not_to_have_attribute("open", "")
    for title in ("List append", "Average", "Remove duplicates"):
        radio = app.page.get_by_role("radiogroup", name="Example", exact=True).get_by_role("radio", name=title, exact=True)
        expect(radio).to_be_visible()
        box = radio.bounding_box()
        assert box and box["x"] >= 0 and box["x"] + box["width"] <= app.page.viewport_size["width"] + 1
    app.open_sidebar()
    expect(app.page.get_by_role("img", name="CodeLens", exact=True)).to_be_visible()
    app.screenshot("sidebar.png")
    app.close_sidebar()
    app.mode(GUIDED)
    app.predict("A prediction to compare with the observed output")
    app.run()
    evidence = app.section("execution_evidence")
    first = evidence.get_by_role("heading", name="Submitted prediction", exact=True).bounding_box()
    second = evidence.get_by_role("heading", name="stdout", exact=True).bounding_box()
    assert first and second
    if app.mobile:
        assert second["y"] > first["y"] + first["height"]
    else:
        assert second["x"] > first["x"] + first["width"]
    dimensions = app.page.evaluate("({width: innerWidth, content: document.documentElement.scrollWidth})")
    assert dimensions["content"] <= dimensions["width"]
    app.screenshot("comparison.png", "execution_evidence")


@pytest.mark.committed_checkout
def test_committed_checkout_starts_without_local_untracked_files(app, expect):
    """A reviewer should be able to start the version present in Git."""
    expect(app.page.get_by_role("button", name="Run approved example", exact=True)).to_be_enabled()
    expect(app.page.get_by_role("img", name="CodeLens", exact=True)).to_be_visible()
