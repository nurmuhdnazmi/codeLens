"""Real server and isolated browser fixtures; production code is not patched."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tarfile
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    setattr(item, "rep_" + call.when, outcome.get_result())


@pytest.fixture(scope="session")
def evidence_root(request):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = Path(request.config.getoption("--e2e-artifacts")) / f"{stamp}-{os.getpid()}"
    path.mkdir(parents=True, exist_ok=False)
    print(f"\nE2E evidence: {path.resolve()}")
    return path


def start_server(root, log_path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    # Do not inherit the parent process's real OR synthetic API keys.
    allowed = ("PATH", "HOME", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "WINDIR", "USERPROFILE")
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env["PYTHONUNBUFFERED"] = "1"
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app.py",
             "--server.address=127.0.0.1", f"--server.port={port}",
             "--server.headless=true", "--browser.gatherUsageStats=false",
             "--server.fileWatcherType=none"],
            cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        )
        url = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 40
            while True:
                if process.poll() is not None:
                    pytest.fail(f"Streamlit exited during startup. See {log_path}")
                try:
                    with urlopen(url + "/_stcore/health", timeout=1) as response:
                        if response.read().strip() == b"ok":
                            break
                except (URLError, OSError):
                    pass
                if time.monotonic() >= deadline:
                    pytest.fail(f"Streamlit did not become healthy. See {log_path}")
                time.sleep(0.1)  # Server health polling only; browser actions use auto-waiting.
            yield url
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.fixture(scope="session")
def streamlit_url(evidence_root):
    yield from start_server(ROOT, evidence_root / "streamlit.log")


@pytest.fixture(scope="session")
def committed_checkout_url(evidence_root, tmp_path_factory):
    root = tmp_path_factory.mktemp("codelens-committed-checkout")
    archive = root / "repository.tar"
    subprocess.run(["git", "archive", "HEAD", "-o", str(archive)], cwd=ROOT, check=True)
    with tarfile.open(archive) as source:
        source.extractall(root, filter="data")
    yield from start_server(root, evidence_root / "committed-checkout.log")


@pytest.fixture(scope="session")
def expect():
    try:
        from playwright.sync_api import expect as browser_expect
    except ImportError:
        pytest.fail('Install browser dependencies: python -m pip install -e ".[dev,e2e]"')
    browser_expect.set_options(timeout=10_000)
    return browser_expect


@pytest.fixture(scope="session")
def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.fail('Install browser dependencies: python -m pip install -e ".[dev,e2e]"')
    with sync_playwright() as playwright:
        if not Path(playwright.chromium.executable_path).is_file():
            pytest.fail("Install the matching browser: python -m playwright install chromium")
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture(params=["desktop", "mobile"])
def viewport(request):
    return request.param


class CodeLensUI:
    """Actions use accessible names; named application containers scope evidence."""

    def __init__(self, page, expect, directory, viewport):
        self.page = page
        self.expect = expect
        self.directory = directory
        self.mobile = viewport == "mobile"
        self.download_count = 0

    def section(self, key):
        # st-key-* is Streamlit's documented public class for an explicit key.
        return self.page.locator(f".st-key-{key}")

    def state(self, value):
        caption = self.section("code_review").get_by_text(f"Attempt state: {value}", exact=True)
        # Streamlit briefly retains old elements during progressive rerenders.
        # Require that they have been removed, rather than choosing .first.
        self.expect(caption).to_have_count(1)
        self.expect(caption).to_be_visible()

    def open_sidebar(self):
        button = self.page.get_by_role("button", name="Expand sidebar", exact=True)
        if button.is_visible():
            button.click()

    def close_sidebar(self):
        if self.mobile:
            button = self.page.get_by_role("button", name="Collapse sidebar", exact=True)
            if button.is_visible():
                button.click()

    def mode(self, value):
        self.open_sidebar()
        group = self.page.get_by_role("radiogroup", name="Mode", exact=True)
        group.get_by_text(value, exact=True).click()
        self.expect(group.get_by_role("radio", name=value, exact=True)).to_be_checked()
        self.close_sidebar()
        self.state("ready")
        self.expect(self.page.get_by_role("textbox")).to_have_count(1 if value == "Predict–Explain–Verify" else 0)

    def example(self, title):
        group = self.page.get_by_role("radiogroup", name="Example", exact=True)
        group.get_by_text(title, exact=True).click()
        self.expect(group.get_by_role("radio", name=title, exact=True)).to_be_checked()
        heading = self.page.get_by_role("heading", name=title, exact=True, level=1)
        self.expect(heading).to_have_count(1)
        self.expect(heading).to_be_visible()
        self.state("ready")

    def feedback_mode(self, value):
        self.open_sidebar()
        group = self.page.get_by_role("radiogroup", name="Feedback", exact=True)
        group.get_by_text(value, exact=True).click()
        self.expect(group.get_by_role("radio", name=value, exact=True)).to_be_checked()
        self.close_sidebar()
        # Both modes display "ready". Wait for the selected mode in the
        # last-rendered metrics panel so a pending reset cannot erase input
        # typed against the previous frame.
        panel = self.expander("Current-attempt metrics")
        if panel.get_attribute("open") is None:
            panel.locator("summary").click()
        pattern = r'"feedback_mode"\s*:\s*' + re.escape(json.dumps(value))
        self.expect(panel).to_contain_text(re.compile(pattern))
        self.state("ready")

    def reset(self):
        self.open_sidebar()
        self.page.get_by_role("button", name="Start new attempt", exact=True).click()
        self.close_sidebar()
        self.state("ready")

    def predict(self, value):
        self.page.get_by_role("textbox").fill(value)

    def run(self):
        self.page.get_by_role("button", name="Run approved example", exact=True).click()
        self.state("completed")
        self.expect(self.section("execution_evidence")).to_be_visible()

    def explain(self):
        self.page.get_by_role("button", name="Explain my prediction", exact=True).click()
        self.state("feedback_ready")

    def select_assessment(self, choice):
        self.section("fix_assessment").get_by_text(choice, exact=True).click()
        self.expect(self.section("fix_assessment").get_by_role("radio", name=choice, exact=True)).to_be_checked()

    def assess(self, choice):
        self.select_assessment(choice)
        self.page.get_by_role("button", name="Submit assessment", exact=True).click()
        self.state("verified")

    def expander(self, title):
        return self.page.locator("details").filter(has=self.page.locator("summary").filter(has_text=title))

    def metrics(self, state=None, example_id=None, **expected):
        panel = self.expander("Current-attempt metrics")
        summary = panel.locator("summary")
        if panel.get_attribute("open") is None:
            summary.click()
        if state is not None:
            self.expect(panel).to_contain_text(re.compile(r'"state"\s*:\s*"' + re.escape(state) + '"'))
        if example_id is not None:
            self.expect(panel).to_contain_text(re.compile(r'"example_id"\s*:\s*"' + re.escape(example_id) + '"'))
        for key, value in expected.items():
            pattern = re.escape(json.dumps(key)) + r"\s*:\s*" + re.escape(json.dumps(value))
            self.expect(panel).to_contain_text(re.compile(pattern))
        with self.page.expect_download() as pending:
            panel.get_by_role("button", name="Download metrics JSON", exact=True).click()
        download = pending.value
        assert download.suggested_filename == "codelens-attempt.json"
        self.download_count += 1
        path = self.directory / f"metrics-{self.download_count}.json"
        download.save_as(path)
        return json.loads(path.read_text())

    def screenshot(self, name, section=None):
        path = self.directory / name
        if section:
            self.section(section).screenshot(path=str(path))
        else:
            self.page.screenshot(path=str(path), full_page=True)
        return path


@pytest.fixture
def app(request, browser, streamlit_url, viewport, evidence_root, expect):
    name = re.sub(r"[^a-zA-Z0-9_.-]", "_", request.node.name)
    directory = evidence_root / name
    directory.mkdir()
    size = {"width": 1440, "height": 1000} if viewport == "desktop" else {"width": 390, "height": 844}
    context = browser.new_context(viewport=size, is_mobile=viewport == "mobile", has_touch=viewport == "mobile", locale="en-GB")
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    blocked = []

    def local_only(route):
        if urlsplit(route.request.url).hostname in ("127.0.0.1", "localhost"):
            route.continue_()
        else:
            blocked.append(urlsplit(route.request.url).hostname)
            route.abort()

    context.route("**/*", local_only)
    page = context.new_page()
    page.set_default_timeout(10_000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    ui = CodeLensUI(page, expect, directory, viewport)
    loaded = False
    try:
        if request.node.get_closest_marker("committed_checkout"):
            streamlit_url = request.getfixturevalue("committed_checkout_url")
        page.goto(streamlit_url)
        if not request.node.get_closest_marker("committed_checkout"):
            expect(page.get_by_role("button", name="Run approved example", exact=True)).to_be_enabled()
        loaded = True
        yield ui
    finally:
        failed = not loaded or any(getattr(request.node, "rep_" + phase, None) and getattr(request.node, "rep_" + phase).failed for phase in ("setup", "call"))
        capture_errors = []
        if failed or errors or blocked:
            try:
                page.screenshot(path=str(directory / "failure.png"), full_page=True)
                (directory / "page.yml").write_text(page.locator("body").aria_snapshot())
            except Exception as error:
                capture_errors.append(str(error))
            context.tracing.stop(path=str(directory / "trace.zip"))
        else:
            context.tracing.stop()
        (directory / "browser.json").write_text(json.dumps({"viewport": size, "browser_version": browser.version, "page_errors": errors, "blocked_external_hosts": blocked, "capture_errors": capture_errors}, indent=2))
        context.close()
        if not failed:
            assert not errors, f"Browser JavaScript errors: {errors}"
            assert not blocked, f"Unexpected external browser requests were blocked: {blocked}"
