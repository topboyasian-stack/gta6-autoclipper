import unittest
from pathlib import Path

from scripts.flow_automator import FlowAutomationError, parser, validate_expected_account


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

    def test_account_identity_is_verified_before_flow_generation(self):
        source = (ROOT / "scripts" / "flow_automator.py").read_text(encoding="utf-8")
        browser_start = source.index("async def __aenter__(self):")
        browser_end = source.index("async def __aexit__(self", browser_start)
        browser_entry = source[browser_start:browser_end]
        self.assertIn("await self.verify_account(expected_account)", browser_entry)
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


if __name__ == "__main__":
    unittest.main()
