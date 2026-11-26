"""Credit-guarded, resumable Google Flow image/video worker for Colab."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    from .flow_credits import FlowCreditLedger, episode_credit_plan
except ImportError:  # The Colab runner invokes this file directly as a script.
    from flow_credits import FlowCreditLedger, episode_credit_plan

FLOW_URL = "https://labs.google/fx/tools/flow"
LOG = logging.getLogger("flow_automator")


class FlowAutomationError(RuntimeError):
    pass


def retry_key(events: list[dict], field: str, base_key: str, retryable_status: str) -> str:
    """Only retry recorded attempts known to have failed before a billable submission."""
    previous = [e for e in events if e.get(field) == base_key or str(e.get(field, "")).startswith(base_key + ":retry-")]
    if not previous:
        return base_key
    if any(e.get("status") != retryable_status for e in previous):
        return base_key  # Ledger idempotency will block submitted/unknown/completed attempts.
    return f"{base_key}:retry-{len(previous) + 1}"


def read_json(path: Path, kind=dict):
    if not path.is_file() or not path.stat().st_size:
        raise FileNotFoundError(f"Required Flow input missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, kind):
        raise FlowAutomationError(f"Expected {kind.__name__} in {path}")
    return value


def write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def validate_expected_account(value: str) -> str:
    """Require an explicit, well-formed email for the Google account expected in Flow."""
    email = str(value or "").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise FlowAutomationError(
            "An exact expected Google account email is required. "
            "No Flow generation can proceed without account verification."
        )
    return email



CHROMIUM_PROFILE_LOCKS = ("SingletonLock", "SingletonCookie", "SingletonSocket")
CHROMIUM_PROFILE_IGNORES = {
    *CHROMIUM_PROFILE_LOCKS,
    "DevToolsActivePort",
    "Crashpad",
    "BrowserMetrics",
    "GPUCache",
    "Code Cache",
    "Cache",
    "Media Cache",
    "DawnCache",
    "GrShaderCache",
    "ShaderCache",
    "component_crx_cache",
    "Crash Reports",
}


def chromium_profile_is_locked(profile_dir: Path) -> bool:
    """Detect Chromium singleton markers without deleting or modifying them."""
    import os
    profile_dir = Path(profile_dir)
    return any(os.path.lexists(profile_dir / name) for name in CHROMIUM_PROFILE_LOCKS)


def _ignore_chromium_profile_cache(_directory: str, names: list[str]) -> set[str]:
    """Exclude runtime locks and disposable caches from profile snapshots."""
    return {name for name in names if name in CHROMIUM_PROFILE_IGNORES}


class ChromiumProfileStore:
    """Stage a Drive-backed browser profile locally and snapshot it after Chromium exits.

    Chromium must not hold its singleton lock on Google Drive/FUSE: Colab sessions can
    run on different hosts, leaving a remote-host lock that prevents the next launch.
    """

    def __init__(self, persisted_profile_dir: Path):
        import tempfile
        import uuid

        self.persisted_dir = Path(persisted_profile_dir).expanduser().resolve()
        self.pointer_path = self.persisted_dir.with_name(self.persisted_dir.name + ".active.json")
        self.snapshots_dir = self.persisted_dir.with_name(self.persisted_dir.name + "_sessions")
        self.runtime_dir = Path(tempfile.mkdtemp(prefix="google-flow-chromium-"))
        self.source_dir: Path | None = None
        self.source_locked = False
        self._prepared = False
        self._uuid = uuid.uuid4().hex

    def _select_source(self) -> Path:
        if self.pointer_path.is_file():
            try:
                pointer = json.loads(self.pointer_path.read_text(encoding="utf-8"))
                candidate = Path(pointer.get("profile_dir", "")).expanduser().resolve()
                snapshots_root = self.snapshots_dir.resolve()
                if candidate.is_dir() and candidate.parent == snapshots_root:
                    return candidate
                LOG.warning(
                    "[AUTH] Ignoring invalid or missing saved profile pointer: %s",
                    self.pointer_path,
                )
            except Exception as exc:
                LOG.warning("[AUTH] Could not read saved profile pointer: %s", exc)
        return self.persisted_dir

    def prepare(self) -> Path:
        """Create the local Chromium profile, copying only an unlocked saved profile."""
        if self._prepared:
            return self.runtime_dir
        self._prepared = True
        self.source_dir = self._select_source()
        if chromium_profile_is_locked(self.source_dir):
            self.source_locked = True
            LOG.warning(
                "[AUTH] A Chromium lock marker exists in the saved Drive profile (%s). "
                "It may belong to another Colab runtime. Preserving it untouched and "
                "starting an isolated local profile; Google sign-in may be required.",
                self.source_dir,
            )
            return self.runtime_dir

        if self.source_dir.is_dir():
            try:
                shutil.copytree(
                    self.source_dir,
                    self.runtime_dir,
                    dirs_exist_ok=True,
                    ignore=_ignore_chromium_profile_cache,
                )
                LOG.info(
                    "[AUTH] Copied saved browser state from Drive to local Colab storage: %s",
                    self.source_dir,
                )
            except Exception as exc:
                # A damaged or partially synced profile must not block browser startup.
                # Keep the source intact and fall back to a clean local profile.
                LOG.warning(
                    "[AUTH] Saved profile could not be staged (%s). Starting a clean local profile; "
                    "the Drive copy remains untouched.",
                    exc,
                )
                for child in self.runtime_dir.iterdir():
                    if child.is_dir() and not child.is_symlink():
                        shutil.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)
        else:
            LOG.info("[AUTH] No saved Flow profile found; creating a new local browser profile.")
        return self.runtime_dir

    def persist(self) -> None:
        """Write a versioned, unlocked profile snapshot to Drive after Chromium has closed."""
        import uuid
        if not self.runtime_dir.is_dir():
            return
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        snapshot = self.snapshots_dir / f"session-{stamp}-{self._uuid[:8]}"
        staging = self.snapshots_dir / f".staging-{uuid.uuid4().hex}"
        try:
            shutil.copytree(
                self.runtime_dir,
                staging,
                ignore=_ignore_chromium_profile_cache,
            )
            # The browser is already closed, so this snapshot should contain no
            # Chromium singleton locks. Remove any defensive leftovers before publish.
            for name in CHROMIUM_PROFILE_LOCKS:
                (staging / name).unlink(missing_ok=True)
            staging.replace(snapshot)
            write_json(
                self.pointer_path,
                {
                    "profile_dir": str(snapshot),
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "storage": "google_drive_snapshot",
                },
            )
            LOG.info("[AUTH] Saved closed browser profile snapshot for the next run: %s", snapshot)
        except Exception as exc:
            shutil.rmtree(staging, ignore_errors=True)
            LOG.warning(
                "[AUTH] Browser session worked, but its profile snapshot could not be saved to Drive: %s",
                exc,
            )
        finally:
            shutil.rmtree(self.runtime_dir, ignore_errors=True)

    def discard(self) -> None:
        """Remove a local staging profile when Chromium never started."""
        shutil.rmtree(self.runtime_dir, ignore_errors=True)

def normalise_image(path: Path):
    from PIL import Image, ImageOps
    with Image.open(path) as im:
        im = im.convert("RGB")
        if path.parent.name != "character_references":
            im = ImageOps.fit(im, (1920, 1080), method=Image.Resampling.LANCZOS)
        im.save(path, format="PNG", optimize=True)
    if path.stat().st_size < 10_000:
        raise FlowAutomationError(f"Invalid image download: {path}")


def validate_video(path: Path) -> float:
    if not path.is_file() or path.stat().st_size < 50_000:
        raise FlowAutomationError(f"Invalid or missing video download: {path}")
    probe = shutil.which("ffprobe")
    if not probe:
        raise FlowAutomationError("ffprobe is required.")
    result = subprocess.run(
        [probe, "-v", "error", "-show_entries", "format=duration", "-of",
         "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode:
        raise FlowAutomationError("ffprobe rejected Flow video: " + result.stderr[-1000:])
    duration = float(result.stdout.strip())
    if duration < 2:
        raise FlowAutomationError(f"Downloaded video duration is only {duration:.2f}s.")
    return duration


class FlowBrowser:
    def __init__(self, args, ledger):
        self.args, self.ledger = args, ledger
        self.pw = self.context = self.page = None
        self.last_submission = False
        self.profile_store = None
        self.browser_started = False
        self.diag = Path(args.output) / "flow_diagnostics"
        self.diag.mkdir(parents=True, exist_ok=True)

    async def __aenter__(self):
        from playwright.async_api import async_playwright
        import os
        expected_account = validate_expected_account(getattr(self.args, "expected_account", ""))
        if not os.environ.get("DISPLAY"):
            raise FlowAutomationError("No browser display found. Start the Colab noVNC display first.")
        self.profile_store = ChromiumProfileStore(self.args.profile_dir)
        runtime_profile = self.profile_store.prepare()
        LOG.info(
            "[AUTH] Starting branded Google Chrome with an isolated local profile: %s "
            "(persistent Drive store: %s). The user will complete Google sign-in manually "
            "in the visible browser before any automated Flow actions.",
            runtime_profile,
            self.args.profile_dir,
        )
        self.pw = await async_playwright().start()
        try:
            self.context = await self.pw.chromium.launch_persistent_context(
                user_data_dir=str(runtime_profile),
                channel="chrome",
                headless=False,
                accept_downloads=True,
                viewport={"width": 1440, "height": 900},
                ignore_default_args=["--enable-automation"],
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            self.browser_started = True
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
            self.page.set_default_timeout(15_000)
            browser_state = await self.page.evaluate(
                "() => ({webdriver: navigator.webdriver, userAgent: navigator.userAgent})"
            )
            if browser_state.get("webdriver") is True or "HeadlessChrome" in str(browser_state.get("userAgent", "")):
                raise FlowAutomationError(
                    "Branded Chrome still reports an automation-controlled or headless browser state. "
                    "Google sign-in has not been attempted; check the Chrome launch configuration."
                )
            LOG.info(
                "[AUTH] Browser readiness: branded Chrome visible; navigator.webdriver=%s; userAgent=%s",
                browser_state.get("webdriver"),
                browser_state.get("userAgent"),
            )
            LOG.info("[AUTH] Opening Google Flow. Expected account: %s", expected_account)
            await self.page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=90_000)
            await self._login()
            await self.verify_account(expected_account)
            await self.page.wait_for_timeout(1500)
            if not await self._prompt(False):
                LOG.info("[FLOW] Opening a new Flow project/composer.")
                await self._click([r"new project", r"create project", r"start a new project"], False)
                await self.page.wait_for_timeout(2500)
            if not await self._prompt(False):
                await self.diagnostics("composer_missing")
                raise FlowAutomationError("Flow composer not found. Nothing was generated.")
            LOG.info("[FLOW] Verified account and Flow composer; proceeding to credit checks.")
            return self
        except Exception:
            # __aexit__ is not called when __aenter__ raises, so close explicitly.
            await self._shutdown()
            raise

    async def _shutdown(self):
        closed_cleanly = False
        try:
            if self.context:
                await self.context.close()
                closed_cleanly = True
                self.context = None
            else:
                closed_cleanly = not self.browser_started
        finally:
            if self.pw:
                await self.pw.stop()
                self.pw = None
            if self.profile_store:
                if self.browser_started and closed_cleanly:
                    self.profile_store.persist()
                else:
                    self.profile_store.discard()
                self.profile_store = None
            self.browser_started = False

    async def __aexit__(self, exc_type, exc, tb):
        await self._shutdown()

    async def body(self):
        try:
            return await self.page.locator("body").inner_text(timeout=5000)
        except Exception:
            return ""

    async def _login(self):
        LOG.info("[AUTH] Checking whether this saved browser profile is signed in; use the embedded browser if sign-in or account selection appears.")
        start, announced, last_notice = time.monotonic(), False, 0.0
        while time.monotonic() - start < self.args.login_timeout:
            url, body = self.page.url.lower(), (await self.body()).lower()
            signed_in = "labs.google" in url and "accounts.google.com" not in url
            login_screen = "accounts.google.com" in url or ("sign in" in body and ("password" in body or "email or phone" in body))
            if signed_in and not login_screen:
                LOG.info("[AUTH] Flow page is open; the active Google account still needs explicit verification.")
                return
            if login_screen and not announced:
                LOG.warning("[AUTH] SIGN-IN REQUIRED: complete sign-in inside the embedded browser, then select the expected account.")
                announced = True
            now = time.monotonic()
            if now - last_notice >= 15:
                LOG.info(
                    "[AUTH] Still checking sign-in state; %ds remain. Look at the embedded browser for a sign-in, security, or account-selection screen. No generation has been submitted.",
                    max(0, int(self.args.login_timeout - (now - start))),
                )
                last_notice = now
            await self.page.wait_for_timeout(1000)
        await self.diagnostics("login_timeout")
        raise FlowAutomationError("Google sign-in timed out. No generation was submitted; the Drive browser profile is retained for the next run.")

    async def verify_account(self, expected_account: str):
        """Fail closed unless the expected email is visible in the active Google account UI."""
        expected = validate_expected_account(expected_account).casefold()
        account_selector = (
            'button[aria-label*="Google Account" i], a[aria-label*="Google Account" i], '
            '[role="button"][aria-label*="Google Account" i], '
            'button[title*="Google Account" i], a[title*="Google Account" i], '
            '[role="button"][title*="Google Account" i]'
        )

        async def visible_identity_text():
            fragments = [await self.body()]
            nodes = self.page.locator("button, a, [role='button'], [role='menuitem'], [role='dialog'], img")
            for i in range(min(await nodes.count(), 250)):
                node = nodes.nth(i)
                try:
                    if not await node.is_visible():
                        continue
                    for attr in ("aria-label", "title", "alt", "data-email"):
                        value = await node.get_attribute(attr)
                        if value:
                            fragments.append(value)
                    if await node.evaluate("(el) => !['IMG','SVG'].includes(el.tagName)"):
                        text = (await node.inner_text()).strip()
                        if text:
                            fragments.append(text)
                except Exception:
                    continue
            return "\\n".join(fragments).casefold()

        async def direct_account_identity():
            controls = self.page.locator(account_selector)
            values = []
            clickable = None
            for i in range(min(await controls.count(), 20)):
                node = controls.nth(i)
                try:
                    if not await node.is_visible():
                        continue
                    parts = [await node.get_attribute(attr) or "" for attr in ("aria-label", "title", "alt", "data-email")]
                    values.extend(parts)
                    if clickable is None:
                        clickable = node
                except Exception:
                    continue
            return " ".join(values).casefold(), clickable

        direct_identity, clickable = await direct_account_identity()
        if expected in direct_identity:
            LOG.info("[AUTH] VERIFIED active Google account from its account control: %s", expected_account)
            return

        if clickable is not None:
            try:
                LOG.info("[AUTH] Opening Google account menu to confirm account identity.")
                await clickable.click()
                await self.page.wait_for_timeout(500)
            except Exception as exc:
                LOG.warning("[AUTH] Could not open the Google account menu yet: %s", exc)

        # Keep the browser interactive while the user signs in or switches accounts.
        # Nothing in this method submits a billable generation.
        deadline = time.monotonic() + 180
        last_notice = 0.0
        LOG.warning(
            "[AUTH] Expected account is not confirmed yet. In the embedded browser, sign in or switch to %s. "
            "Generation remains blocked until this exact account is verified.",
            expected_account,
        )
        while time.monotonic() < deadline:
            direct_identity, _ = await direct_account_identity()
            evidence = await visible_identity_text()
            account_menu_visible = any(
                marker in evidence
                for marker in ("manage your google account", "sign out", "sign out of")
            )
            if expected in direct_identity or (expected in evidence and account_menu_visible):
                LOG.info("[AUTH] VERIFIED active Google account: %s", expected_account)
                return
            now = time.monotonic()
            if now - last_notice >= 15:
                LOG.info(
                    "[AUTH] Still waiting for account confirmation (%ds remaining); no generation has been submitted.",
                    max(0, int(deadline - now)),
                )
                last_notice = now
            await self.page.wait_for_timeout(2000)

        await self.diagnostics("account_unverified")
        raise FlowAutomationError(
            f"Could not verify that Google Flow is using {expected_account!r}. "
            "No image or video generation was submitted. The browser profile was retained; "
            "check the account menu and resume with the same expected email."
        )

    async def diagnostics(self, label: str):
        try:
            await self.page.screenshot(path=str(self.diag / f"{label}.png"), full_page=True)
        except Exception:
            pass
        data = {"url": self.page.url, "title": await self.page.title(), "visible_text": (await self.body())[:12000], "buttons": [], "inputs": []}
        for selector, key in (("button", "buttons"), ("textarea,[role='textbox'],[contenteditable='true']", "inputs")):
            nodes = self.page.locator(selector)
            for i in range(min(await nodes.count(), 100)):
                node = nodes.nth(i)
                try:
                    if await node.is_visible():
                        data[key].append({
                            "text": (await node.inner_text())[:160],
                            "aria": await node.get_attribute("aria-label"),
                            "placeholder": await node.get_attribute("placeholder"),
                        })
                except Exception:
                    pass
        write_json(self.diag / f"{label}.json", data)
        LOG.info("UI diagnostics saved: %s", self.diag / f"{label}.json")

    async def _buttons(self, patterns):
        nodes = self.page.get_by_role("button")
        matches = []
        regexes = [re.compile(p, re.I) for p in patterns]
        for i in range(await nodes.count()):
            node = nodes.nth(i)
            try:
                if not await node.is_visible():
                    continue
                label = (await node.inner_text()) + " " + (await node.get_attribute("aria-label") or "")
                if any(rx.search(" ".join(label.split())) for rx in regexes):
                    matches.append(node)
            except Exception:
                pass
        return matches

    async def _click(self, patterns, required=True):
        matches = await self._buttons(patterns)
        if not matches:
            if required:
                raise FlowAutomationError(f"Flow control not found: {patterns}")
            return False
        await matches[-1].click()
        await self.page.wait_for_timeout(600)
        return True

    async def _prompt(self, required=True):
        candidates = []
        for selector in ("textarea", "[contenteditable='true']", "[role='textbox']"):
            nodes = self.page.locator(selector)
            for i in range(await nodes.count()):
                node = nodes.nth(i)
                try:
                    if not await node.is_visible() or not await node.is_enabled():
                        continue
                    label = ((await node.get_attribute("placeholder") or "") + " " + (await node.get_attribute("aria-label") or "")).lower()
                    if not any(x in label for x in ("search", "project name", "title", "file name")):
                        candidates.append(node)
                except Exception:
                    pass
        if candidates:
            return candidates[-1]
        if required:
            raise FlowAutomationError("Flow's visible prompt box is missing.")
        return None

    async def _fill_prompt(self, text):
        box = await self._prompt()
        await box.fill(text)
        value = await box.input_value() if await box.evaluate("el => 'value' in el") else await box.inner_text()
        if text[:50] not in value:
            raise FlowAutomationError("Flow did not retain the prompt text.")

    async def mode(self, target):
        if target == "image":
            ok = await self._click([r"^image$", r"image generation", r"create image"], False)
            if not ok:
                tab = self.page.get_by_role("tab", name=re.compile("image", re.I))
                if not await tab.count():
                    await self.diagnostics("image_mode_missing")
                    raise FlowAutomationError("Flow image mode was not found.")
                await tab.first.click()
        else:
            ok = await self._click([r"frames to video", r"image to video"], False)
            if not ok:
                ok = await self._click([r"^video$", r"create video"], False)
                if not ok:
                    tab = self.page.get_by_role("tab", name=re.compile("video", re.I))
                    if not await tab.count():
                        await self.diagnostics("video_mode_missing")
                        raise FlowAutomationError("Flow video mode was not found.")
                    await tab.first.click()
                await self._click([r"frames to video", r"image to video"], False)
        await self.page.wait_for_timeout(700)

    async def model(self, model):
        await self._click([r"model", r"veo", r"nano banana", r"settings"], False)
        if model.lower().startswith("veo 3.1") and "lite" in model.lower():
            option = self.page.get_by_text(re.compile(r"^Veo\s+3\.1\s*-?\s*Lite(?:\s*\(.*\))?$", re.I))
        else:
            option = self.page.get_by_text(model, exact=True)
        chosen = False
        for i in range(await option.count()):
            item = option.nth(i)
            try:
                if await item.is_visible():
                    await item.click()
                    chosen = True
                    break
            except Exception:
                pass
        if not chosen and not await self._buttons([rf"^{re.escape(model)}$"]):
            await self.diagnostics("model_not_found")
            raise FlowAutomationError(f"Flow did not expose exact model {model!r}. No generation submitted.")
        await self.page.wait_for_timeout(700)
        body = await self.body()
        verified = model.lower() in body.lower()
        if model.lower().startswith("veo 3.1") and "lite" in model.lower():
            verified = bool(re.search(r"veo\s+3\.1\s*-?\s*lite", body, re.I))
        if not verified:
            await self.diagnostics("model_unverified")
            raise FlowAutomationError(f"Selected model {model!r} could not be verified.")

    async def duration(self, seconds):
        rx = re.compile(rf"^{seconds}\s*(?:s|sec|secs|seconds)$", re.I)
        candidates = []
        for role in ("radio", "button", "option"):
            nodes = self.page.get_by_role(role, name=rx)
            for i in range(await nodes.count()):
                node = nodes.nth(i)
                try:
                    if await node.is_visible():
                        candidates.append(node)
                except Exception:
                    pass
        if not candidates:
            await self.diagnostics("duration_missing")
            raise FlowAutomationError(f"Flow did not expose an accessible {seconds}s duration.")
        node = candidates[-1]
        current = " ".join((await node.get_attribute(k) or "") for k in ("aria-checked", "aria-selected", "aria-pressed", "data-state", "class")).lower()
        if not any(x in current for x in ("true", "checked", "selected", "active")):
            await node.click()
        await self.page.wait_for_timeout(350)
        state = " ".join((await node.get_attribute(k) or "") for k in ("aria-checked", "aria-selected", "aria-pressed", "data-state", "class")).lower()
        if not any(x in state for x in ("true", "checked", "selected", "active")):
            await self.diagnostics("duration_unverified")
            raise FlowAutomationError("Could not verify the selected duration. No video submitted.")

    async def attach(self, path):
        files = self.page.locator("input[type='file']")
        for i in range(await files.count()):
            item = files.nth(i)
            accept = (await item.get_attribute("accept") or "").lower()
            if not accept or "image" in accept or "*" in accept:
                await item.set_input_files(str(path))
                await self.page.wait_for_timeout(1200)
                return
        buttons = await self._buttons([r"upload", r"add image", r"add frame", r"ingredients", r"add media"])
        if not buttons:
            await self.diagnostics("upload_missing")
            raise FlowAutomationError("Flow frame upload control was not found.")
        async with self.page.expect_file_chooser(timeout=10000) as event:
            await buttons[-1].click()
        chooser = await event.value
        await chooser.set_files(str(path))
        await self.page.wait_for_timeout(1200)

    async def one_output(self):
        for selector in ("select", "input[type='number']"):
            nodes = self.page.locator(selector)
            for i in range(await nodes.count()):
                node = nodes.nth(i)
                try:
                    if not await node.is_visible():
                        continue
                    label = ((await node.get_attribute("aria-label") or "") + " " + (await node.get_attribute("name") or "") + " " + (await node.inner_text())).lower()
                    if re.search(r"output|variation|video|result|count", label):
                        if selector == "select":
                            await node.select_option(label="1")
                        else:
                            await node.fill("1")
                except Exception:
                    pass
        if re.search(r"\b[2-4]\s+(?:videos|outputs|variations)\b", (await self.body()).lower()):
            await self.diagnostics("multiple_outputs")
            raise FlowAutomationError("Flow appears configured for multiple outputs. Stopped before Generate.")

    async def balance(self):
        LOG.info("[BALANCE] Reading the live Google Flow credit balance before any submission.")
        patterns = (
            r"(?:remaining|available|balance)\D{0,30}([\d,]+)\s*(?:google flow\s*)?credits?",
            r"([\d,]+)\s*(?:google flow\s*)?credits?\s*(?:remaining|available|left)",
            r"flow\s*(?:and|&)\s*ai credits?\D{0,20}([\d,]+)",
            r"(?:google\s+)?flow credits?\D{0,20}([\d,]+)",
            r"^\s*([\d,]+)\s+(?:google flow )?credits?\s*$",
        )
        async def parse():
            text = await self.body()
            for pattern in patterns:
                m = re.search(pattern, text, re.I | re.M)
                if m:
                    return int(m.group(1).replace(",", ""))
            return None
        value = await parse()
        if value is not None:
            LOG.info("[BALANCE] Verified live balance: %d Flow credits.", value)
            return value
        await self._click([r"account", r"profile", r"credit", r"balance"], False)
        await self.page.wait_for_timeout(700)
        value = await parse()
        if value is not None:
            LOG.info("[BALANCE] Verified live balance: %d Flow credits.", value)
            return value
        await self.diagnostics("credit_balance_unreadable")
        raise FlowAutomationError("Live Flow balance is unreadable; no generation can safely proceed.")

    async def generate_and_download(self, destination: Path, media_type: str):
        tag = media_type.upper()
        before = len(await self._buttons([r"download"]))
        buttons = await self._buttons([r"^generate$", r"generate image", r"generate video", r"^create$"])
        if not buttons or not await buttons[-1].is_enabled():
            await self.diagnostics("generate_unavailable")
            raise FlowAutomationError("Generate is not available; no request was submitted.")
        LOG.info("[%s] SUBMITTING one output now: %s", tag, destination.name)
        self.last_submission = True  # Treat click timeouts as potentially billable; never auto-retry them.
        await buttons[-1].click()
        LOG.info("[%s] Generate clicked; waiting for Flow to finish. Timeout: %ds.", tag, self.args.render_timeout)
        destination.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.args.render_timeout
        started = time.monotonic()
        last_progress = started
        download_button = None
        while time.monotonic() < deadline:
            current = await self._buttons([r"download"])
            if len(current) > before:
                download_button = current[-1]
                break
            now = time.monotonic()
            if now - last_progress >= 30:
                LOG.info("[%s] Still rendering %s (%.0fs elapsed / %ds max).",
                         tag, destination.name, now - started, self.args.render_timeout)
                last_progress = now
            await self.page.wait_for_timeout(2000)
        if download_button is None:
            await self.diagnostics(f"{media_type}_download_timeout")
            raise FlowAutomationError(f"No new Flow Download control appeared within {self.args.render_timeout}s. Job status is uncertain; do not retry automatically.")
        LOG.info("[%s] Render result appeared; downloading %s.", tag, destination.name)
        async with self.page.expect_download(timeout=45000) as event:
            await download_button.click()
        download = await event.value
        suffix = Path(download.suggested_filename or destination.name).suffix or destination.suffix
        temp = destination.with_suffix(suffix + ".part")
        await download.save_as(str(temp))
        saved = temp.with_suffix(suffix)
        temp.replace(saved)
        LOG.info("[%s] Download saved to %s.", tag, saved)
        return saved

    async def make_image(self, item, project_id):
        path = Path(item["output"])
        if path.is_file() and path.stat().st_size > 10000:
            LOG.info("[IMAGE] Reusing saved image: %s", path.name)
            return False
        LOG.info("[IMAGE] Preparing image asset %s (%s).", item.get("key", path.stem), item.get("kind", "asset"))
        import hashlib
        key = f"{project_id}:{item['kind']}:{item['key']}:{hashlib.sha256(item['prompt'].encode()).hexdigest()[:16]}"
        key = retry_key(self.ledger.data["image_events"], "image_key", key, "failed_no_quota_charge")
        self.last_submission = False
        reserve = self.ledger.reserve_image_generation(
            image_key=key, output_path=str(path), model=self.args.image_model,
        )
        if reserve["status"] == "already_recorded":
            prior = reserve.get("event", {})
            if prior.get("status") == "completed" and path.is_file():
                return False
            raise FlowAutomationError(f"Prior image request unresolved for {path.name}; check Flow history before retrying.")
        submitted = False
        try:
            await self.mode("image")
            await self.model(self.args.image_model)
            for reference_path in item.get("reference_images", []):
                reference = Path(reference_path)
                if not reference.is_file() or reference.stat().st_size < 10000:
                    raise FlowAutomationError(
                        f"Character reference is missing or invalid: {reference}. "
                        "The starting frame will not be generated without its continuity reference."
                    )
                await self.attach(reference)
            await self._fill_prompt(item["prompt"])
            await self.one_output()
            saved = await self.generate_and_download(path, "image")
            submitted = True
            if saved != path:
                saved.replace(path)
            normalise_image(path)
            self.ledger.finish_image_generation(key, status="completed", output_path=str(path))
            LOG.info("[IMAGE] %s saved", path.name)
            return True
        except Exception as exc:
            self.ledger.finish_image_generation(key, status="unknown" if self.last_submission else "failed_no_quota_charge", error=str(exc))
            await self.diagnostics("image_failed_" + path.stem)
            raise

    async def make_video(self, scene, project_id):
        path = Path(scene["output_clip"])
        if path.is_file() and path.stat().st_size > 50000:
            LOG.info("[VIDEO] Reusing completed clip: %s", path.name)
            return False
        LOG.info("[VIDEO] Preparing scene %s; no video request has been submitted for this scene yet.", scene.get("scene_id", path.stem))
        frame = Path(scene["starting_frame"])
        if not frame.is_file():
            raise FileNotFoundError(f"Scene starting frame missing: {frame}")
        seconds = int(scene.get("duration_seconds") or self.args.duration_seconds)
        prompt = "\n".join([
            "Visual style: " + scene.get("visual_style", ""),
            scene.get("motion_prompt", ""),
            "Camera: " + scene.get("camera_motion", ""),
            "Continuity: " + scene.get("continuity_notes", ""),
            "Silent visual footage only. No speech, narration, subtitles, titles, logos or text. Preserve the supplied starting-frame composition and recurring character identity.",
        ])
        import hashlib
        key = f"{project_id}:{scene['scene_id']}:{hashlib.sha256(prompt.encode()).hexdigest()[:16]}:{self.args.video_model}:{seconds}"
        key = retry_key(self.ledger.data["events"], "generation_key", key, "failed_no_charge")
        self.last_submission = False
        # Prepare UI before reserving spend: any selector failure is safe to correct and retry.
        await self.mode("video")
        await self.model(self.args.video_model)
        await self.attach(frame)
        await self._fill_prompt(prompt)
        await self.duration(seconds)
        await self.one_output()
        current = await self.balance()
        reservation = self.ledger.reserve_video_generation(
            generation_key=key, scene_id=scene["scene_id"], model=self.args.video_model,
            duration_seconds=seconds, current_balance=current,
            metadata={"project_id": project_id, "output_clip": str(path)},
        )
        if reservation["status"] == "already_recorded":
            prior = reservation.get("event", {})
            if prior.get("status") == "completed" and path.is_file():
                return False
            raise FlowAutomationError(f"Prior generation unresolved for {scene['scene_id']}; reconcile Flow history before retrying.")
        submitted = False
        try:
            saved = await self.generate_and_download(path, "video")
            submitted = True
            if saved.suffix.lower() != ".mp4":
                normalised = path.with_name(path.stem + ".normalised.mp4")
                proc = subprocess.run(
                    ["ffmpeg", "-y", "-i", str(saved), "-c:v", "libx264", "-preset", "veryfast",
                     "-crf", "18", "-c:a", "aac", "-movflags", "+faststart", str(normalised)],
                    capture_output=True, text=True, timeout=600, check=False,
                )
                if proc.returncode or not normalised.is_file():
                    raise FlowAutomationError("Could not convert downloaded Flow video to MP4: " + proc.stderr[-1000:])
                normalised.replace(path)
                saved.unlink(missing_ok=True)
            else:
                saved.replace(path)
            duration = validate_video(path)
            after = None
            try:
                after = await self.balance()
            except Exception:
                pass
            self.ledger.finish_video_generation(key, status="completed", balance_after=after, output_path=str(path))
            LOG.info("[VIDEO] %s saved, %.2fs", path.name, duration)
            return True
        except Exception as exc:
            self.ledger.finish_video_generation(key, status="unknown" if self.last_submission else "failed_no_charge", error=str(exc))
            await self.diagnostics("video_failed_" + scene["scene_id"])
            raise


async def run(args):
    expected_account = validate_expected_account(getattr(args, "expected_account", ""))
    LOG.info("[START] Flow automation starting for expected Google account: %s", expected_account)
    out = Path(args.output).resolve()
    image_plan = read_json(out / "assets_generation_plan.json", list)
    manifest = read_json(out / "flow_upload_manifest.json")
    scenes = [x for x in manifest.get("scenes", []) if isinstance(x, dict)]
    if not scenes:
        raise FlowAutomationError("No scenes are present in flow_upload_manifest.json.")
    for scene in scenes:
        scene["visual_style"] = manifest.get("visual_style", "")
    ledger = FlowCreditLedger(
        Path(args.credit_ledger), cycle_id=args.cycle_id, monthly_credits=args.monthly_credits,
        daily_credits=args.daily_credits, reserve_percent=args.reserve_percent, image_model=args.image_model,
    )
    plan = episode_credit_plan(
        scene_count=len(scenes), monthly_credits=args.monthly_credits, daily_credits=args.daily_credits,
        reserve_percent=args.reserve_percent, target_videos=args.target_videos,
        stretch_videos=args.stretch_videos, model=args.video_model, duration_seconds=args.duration_seconds,
    )
    LOG.info("Credit plan: %s", json.dumps(plan))
    missing_clips = [s for s in scenes if not (Path(s["output_clip"]).is_file() and Path(s["output_clip"]).stat().st_size > 50000)]
    if not missing_clips:
        report = {
            "status": "complete", "episode_title": manifest.get("episode_title"),
            "scene_count": len(scenes), "images_generated_this_run": 0,
            "videos_generated_this_run": 0, "clips_complete": len(scenes), "clips_missing": [],
            "credit_plan": plan, "credit_ledger": ledger.summary(),
            "credit_ledger_path": str(args.credit_ledger), "browser_profile": str(args.profile_dir),
            "diagnostics": str(out / "flow_diagnostics"),
        }
        write_json(out / "flow_automation_report.json", report)
        LOG.info("All scene clips already exist; skipped browser and all generation credits.")
        return report
    async with FlowBrowser(args, ledger) as browser:
        live_balance = await browser.balance()
        reserve = int(plan["monthly_reserve_credits"])
        per_scene = int(plan["credits_per_scene"])
        affordable_scenes = max(0, (live_balance - reserve) // per_scene)
        queue_limit = min(args.max_scenes, 12, affordable_scenes)
        queue = missing_clips[:queue_limit]
        projected = len(queue) * per_scene
        if missing_clips and not queue:
            raise FlowAutomationError(
                f"Flow currently shows {live_balance} credits. The controller protects {reserve}; "
                f"at least {per_scene + reserve} are required for one scene. No video was submitted."
            )
        LOG.info("Batch budget: %d missing clips, %d affordable now, %d queued, %d credits reserved.",
                 len(missing_clips), affordable_scenes, len(queue), reserve)
        # Check exact requested video model before making any images.
        await browser.mode("video")
        await browser.model(args.video_model)
        # Images use Flow's separate daily image allowance, not monthly video credits.
        order = {"character_reference": 0, "starting_frame": 1, "thumbnail": 2}
        image_plan = sorted(
            (a for a in image_plan if isinstance(a, dict) and a.get("prompt") and a.get("output")),
            key=lambda a: (order.get(a.get("kind"), 9), a.get("key", "")),
        )
        images_done = 0
        for item in image_plan:
            if item.get("kind") == "thumbnail" and any(not Path(s["starting_frame"]).is_file() for s in scenes):
                continue
            dest = Path(item["output"])
            if dest.is_file() and dest.stat().st_size > 10000:
                continue
            if images_done >= args.max_images:
                LOG.warning("Image batch cap reached; frames will resume next run.")
                break
            images_done += int(await browser.make_image(item, out.parent.name))
        missing_frames = [s["scene_id"] for s in scenes if not Path(s["starting_frame"]).is_file()]
        if missing_frames:
            raise FlowAutomationError("Starting frames incomplete; no video clips submitted: " + ", ".join(missing_frames))
        videos_done = 0
        for scene in queue:
            videos_done += int(await browser.make_video(scene, out.parent.name))
    still_missing = [s["scene_id"] for s in scenes if not (Path(s["output_clip"]).is_file() and Path(s["output_clip"]).stat().st_size > 50000)]
    report = {
        "status": "partial" if still_missing else "complete", "episode_title": manifest.get("episode_title"),
        "scene_count": len(scenes), "images_generated_this_run": images_done,
        "videos_generated_this_run": videos_done, "clips_complete": len(scenes) - len(still_missing),
        "clips_missing": still_missing, "credit_plan": plan, "credit_ledger": ledger.summary(),
        "credit_ledger_path": str(args.credit_ledger), "browser_profile": str(args.profile_dir),
        "diagnostics": str(out / "flow_diagnostics"),
    }
    write_json(out / "flow_automation_report.json", report)
    LOG.info("Flow report: %s", json.dumps(report, ensure_ascii=False))
    return report


def parser():
    p = argparse.ArgumentParser(description="Credit-guarded Google Flow production")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--profile-dir", type=Path, required=True)
    p.add_argument("--expected-account", default="", help="Exact email address that must be verified in the active Google Flow account menu.")
    p.add_argument("--credit-ledger", type=Path, required=True)
    p.add_argument("--cycle-id", required=True)
    p.add_argument("--monthly-credits", type=int, default=1000)
    p.add_argument("--daily-credits", type=int, default=50)
    p.add_argument("--reserve-percent", type=int, default=10)
    p.add_argument("--target-videos", type=int, default=15)
    p.add_argument("--stretch-videos", type=int, default=20)
    p.add_argument("--video-model", default="Veo 3.1 Lite")
    p.add_argument("--image-model", default="Nano Banana Pro")
    p.add_argument("--duration-seconds", type=int, choices=(4, 6, 8), default=8)
    p.add_argument("--max-scenes", type=int, default=6)
    p.add_argument("--max-images", type=int, default=25)
    p.add_argument("--login-timeout", type=int, default=600)
    p.add_argument("--render-timeout", type=int, default=600)
    return p


def main():
    args = parser().parse_args()
    Path(args.output).mkdir(parents=True, exist_ok=True)
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("Install ffmpeg and ffprobe first.")
    logging.basicConfig(
        level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(Path(args.output) / "flow_automation.log", encoding="utf-8")],
    )
    try:
        result = asyncio.run(run(args))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        LOG.exception("Flow automation stopped safely: %s", exc)
        write_json(Path(args.output) / "flow_automation_error.json", {"error": f"{type(exc).__name__}: {exc}"})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
