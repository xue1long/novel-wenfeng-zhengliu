"""Stage D Task 2: six-stage data contract tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from six_stage_contract import (  # noqa: E402
    ContractError,
    STAGE_DATA_CONTRACT,
    STAGE_ORDER,
    assert_contract_compatibility,
    get_contract,
    stage_index,
    validate_stage_contract,
)


class ContractShapeTests(unittest.TestCase):
    def test_stage_order_is_six(self):
        self.assertEqual(STAGE_ORDER, (
            "write_entry", "scene_design", "character_beats",
            "prose_draft", "style_check", "revision",
        ))
        self.assertEqual(len(STAGE_DATA_CONTRACT), 6)

    def test_required_inputs_are_non_empty_strings(self):
        for stage_id, contract in STAGE_DATA_CONTRACT.items():
            for key in contract.required_inputs:
                self.assertIsInstance(key, str)
                self.assertGreater(len(key), 0, f"{stage_id} has empty required_input")
            self.assertGreater(len(contract.constraints), 0, f"{stage_id} has no constraints")

    def test_stage_index_and_get_contract_round_trip(self):
        for index, stage_id in enumerate(STAGE_ORDER):
            self.assertEqual(stage_index(stage_id), index)
            self.assertEqual(get_contract(stage_id).stage_id, stage_id)


class ValidateStageContractTests(unittest.TestCase):
    def test_write_entry_accepts_empty_inputs(self):
        self.assertEqual(validate_stage_contract("write_entry", set()), [])

    def test_scene_design_missing_user_brief(self):
        errors = validate_stage_contract("scene_design", {"stage_context_input_refs.constraints"})
        self.assertTrue(any("user_brief" in e for e in errors), errors)

    def test_scene_design_complete_inputs(self):
        keys = {
            "stage_context_input_refs.user_brief",
            "stage_context_input_refs.constraints",
        }
        self.assertEqual(validate_stage_contract("scene_design", keys), [])


class CompatibilityTests(unittest.TestCase):
    def test_legal_handoff_legal(self):
        # Each pair must be checked with the cumulative chain outputs so that
        # downstream stages can see upstream keys.
        pairs = [
            ("write_entry", "scene_design", {"stage-context"}),
            ("scene_design", "character_beats", {"stage-context", "scene_plan"}),
            ("character_beats", "prose_draft", {"stage-context", "scene_plan", "character_beats"}),
            ("prose_draft", "style_check", {"stage-context", "scene_plan", "character_beats", "prose_draft"}),
            ("style_check", "revision", {"stage-context", "scene_plan", "character_beats", "prose_draft", "diagnostics"}),
        ]
        for current, nxt, chain in pairs:
            assert_contract_compatibility(current, nxt, chain_outputs=chain)

    def test_legal_handoff_without_chain_outputs_still_passes(self):
        # Without an explicit chain_outputs, the contract still succeeds as long
        # as the *current* stage's output covers the next stage's required
        # inputs. ``write_entry -> scene_design`` works because scene_design
        # needs user_brief + constraints which are entry-supplied.
        assert_contract_compatibility("write_entry", "scene_design")

    def test_cross_stage_skip_is_rejected_by_contract(self):
        # ``write_entry`` does NOT cover scene_plan / character_beats /
        # bundle_mechanisms; the contract layer flags the missing data even
        # though the state-machine layer is the one that flags the handoff
        # illegality.
        with self.assertRaises(ContractError):
            assert_contract_compatibility("write_entry", "prose_draft")

    def test_return_to_compatible(self):
        assert_contract_compatibility(
            "style_check", "scene_design",
            chain_outputs={"scene_plan", "character_beats", "prose_draft"},
        )

    def test_state_machine_layer_is_authoritative_for_handoff_legality(self):
        # The contract module must NOT itself enforce handoff legality. The
        # state-machine layer in Task 3 owns that. The contract only checks
        # the data context.
        assert_contract_compatibility("write_entry", "scene_design")


class ContractCoverageAgainstSpecTests(unittest.TestCase):
    def test_prose_draft_only_uses_approved_or_limited_mechanisms(self):
        contract = get_contract("prose_draft")
        self.assertIn("only_approved_or_limited_mechanisms", contract.constraints)

    def test_style_check_does_not_edit_prose(self):
        contract = get_contract("style_check")
        self.assertIn("diagnose_only", contract.constraints)

    def test_revision_preserves_ending(self):
        contract = get_contract("revision")
        self.assertIn("preserve_user_ending", contract.constraints)


if __name__ == "__main__":
    unittest.main()