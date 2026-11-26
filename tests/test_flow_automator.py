import unittest
from pathlib import Path

from scripts.flow_automator import (
    ChromiumProfileStore,
    FlowAutomationError,
    chromium_profile_is_locked,
    parser,
    validate_expected_account,
)


ROOT = Path(__file__).resolve().parents[1]


class ExpectedFlowAccountTests(unittest.TestCase):
    def test_valid_email_is_trimmed_and_preserved(self):
        self.assertEqual(
            validate_expected_account("  owner@example.com  "),
            "owner@example.com",
        )

    def test_missing_or_malformed_email_is_rejected(self):
        for value in ("", "not-an-email", "owner@", "@example.com", "owner@example"):
            with self.subTest(value=value):
                with self.assertRaises(FlowAutomationError):
                    validate_expected_account(value)

    def test_cli_accepts_required_expected_account_argument(self):
        args = parser().parse_args([
            "--output", "/tmp/output",
            "--workspace", "/tmp/workspace",
            "--profile-dir", "/tmp/profile",
            "--expected-account", "owner@example.com",
            "--credit-ledger", "/tmp/ledger.json",
            "--cycle-id", "test-cycle",
        ])
        self.assertEqual(args.expected_account, "owner@example.com")

    def test_google_signin_uses_branded_chrome_without_playwright_automation_markers(self):
        source = (ROOT / "scripts" / "flow_automator.py").read_text(encoding="utf-8")
        self.assertIn('channel="chrome"', source)
        self.assertIn('ignore_default_args=["--enable-automation"]', source)
        self.assertIn('--disable-blink-features=AutomationControlled', source)
        self.assertIn("user will complete Google sign-in manually", source)
    def test_account_identity_is_verified_before_flow_generation(self):
        source = (ROOT / "scripts" / "flow_automator.py").read_text(encoding="utf-8")
        browser_start = source.index("async def __aenter__(self):")
        browser_end = source.index("async def __aexit__(self", browser_start)
        browser_entry = source[browser_start:browser_end]
        self.assertIn("await self.verify_account(expected_account)", browser_entry)
        self.assertIn("ChromiumProfileStore(self.args.profile_dir)", browser_entry)
        self.assertIn("user_data_dir=str(runtime_profile)", browser_entry)
        self.assertNotIn("user_data_dir=str(self.args.profile_dir)", browser_entry)
        self.assertLess(
            browser_entry.index("await self.verify_account(expected_account)"),
            browser_entry.index("LOG.info(\"[FLOW] Verified account and Flow composer"),
        )
        run_start = source.index("async def run(args):")
        run_end = source.index("\ndef parser():", run_start)
        run_body = source[run_start:run_end]
        self.assertLess(run_body.index("async with FlowBrowser(args, ledger)"), run_body.index("await browser.balance()"))
        self.assertLess(run_body.index("await browser.balance()"), run_body.index("for item in image_plan"))
        self.assertIn("[AUTH] VERIFIED active Google account", source)
        self.assertIn("[BALANCE] Verified live balance", source)
        self.assertIn("Still rendering", source)
        self.assertIn("Still checking sign-in state", source)
        self.assertIn('await self.diagnostics("login_timeout")', source)




class ChromiumProfileStoreTests(unittest.TestCase):
    def test_locked_drive_profile_is_preserved_and_recovered_to_new_snapshot(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "google_flow"
            profile.mkdir()
            (profile / "Cookies").write_text("old-cookie-state", encoding="utf-8")
            (profile / "SingletonLock").write_text("8643\\n1b25013f9cc1", encoding="utf-8")

            self.assertTrue(chromium_profile_is_locked(profile))
            store = ChromiumProfileStore(profile)
            runtime = store.prepare()

            self.assertEqual(list(runtime.iterdir()), [])
            self.assertTrue((profile / "SingletonLock").is_file())
            self.assertEqual((profile / "Cookies").read_text(encoding="utf-8"), "old-cookie-state")

            (runtime / "Preferences").write_text("fresh-session", encoding="utf-8")
            store.persist()

            pointer_path = profile.with_name("google_flow.active.json")
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
            snapshot = Path(pointer["profile_dir"])
            self.assertTrue(snapshot.is_dir())
            self.assertEqual((snapshot / "Preferences").read_text(encoding="utf-8"), "fresh-session")
            self.assertFalse((snapshot / "SingletonLock").exists())
            self.assertTrue((profile / "SingletonLock").exists())

            next_store = ChromiumProfileStore(profile)
            next_runtime = next_store.prepare()
            self.assertEqual(
                (next_runtime / "Preferences").read_text(encoding="utf-8"),
                "fresh-session",
            )
            next_store.discard()

    def test_unlocked_drive_profile_is_copied_to_local_profile_then_snapshotted(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "google_flow"
            profile.mkdir()
            (profile / "Cookies").write_text("signed-in", encoding="utf-8")
            store = ChromiumProfileStore(profile)
            runtime = store.prepare()

            self.assertNotEqual(runtime, profile)
            self.assertEqual((runtime / "Cookies").read_text(encoding="utf-8"), "signed-in")
            self.assertEqual((profile / "Cookies").read_text(encoding="utf-8"), "signed-in")
            (runtime / "Preferences").write_text("changed", encoding="utf-8")
            store.persist()

            pointer = json.loads(
                profile.with_name("google_flow.active.json").read_text(encoding="utf-8")
            )
            snapshot = Path(pointer["profile_dir"])
            self.assertEqual((snapshot / "Cookies").read_text(encoding="utf-8"), "signed-in")
            self.assertEqual((snapshot / "Preferences").read_text(encoding="utf-8"), "changed")
            self.assertFalse(runtime.exists())

    def test_profile_lock_symlink_is_detected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "google_flow"
            profile.mkdir()
            (profile / "SingletonLock").symlink_to("8643")
            self.assertTrue(chromium_profile_is_locked(profile))


if __name__ == "__main__":
    unittest.main()
