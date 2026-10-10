"""Stage D Task 6 tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


class TemplatesReadyTests(unittest.TestCase):
    def test_templates_ready(self):
        import check_stage_d  # noqa: E402
        failures = check_stage_d.check_templates_ready()
        self.assertEqual(failures, [], msg=failures)


class StateMachineCoverageTests(unittest.TestCase):
    def test_state_machine_coverage(self):
        import check_stage_d  # noqa: E402
        failures = check_stage_d.check_state_machine_legal_and_illegal()
        self.assertEqual(failures, [], msg=failures)


class DownstreamInvalidationTests(unittest.TestCase):
    def test_downstream_invalidation(self):
        import check_stage_d  # noqa: E402
        failures = check_stage_d.check_downstream_invalidation()
        self.assertEqual(failures, [], msg=failures)


class GateOutputLanguageTests(unittest.TestCase):
    def test_gate_output_does_not_claim_validated(self):
        """Ruling-D5: the gate must not describe itself as a runtime / effect validator."""
        import check_stage_d  # noqa: E402
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = check_stage_d.main()
        self.assertEqual(rc, 0, msg=buf.getvalue())
        text = buf.getvalue()
        forbidden_words = ("validated", "ready to ship", "effect verified", "production-ready")
        for word in forbidden_words:
            self.assertNotIn(word, text.lower(), f"gate output mentions forbidden word {word!r}")


if __name__ == "__main__":
    unittest.main()
