"""Stage C Task 2: five-dimension extractor tests.

Spec anchor: §4.3 '五个提取器是独立的方法模块,不是并行 Agent'.
"""

from __future__ import annotations

import json
import socket  # used to assert no network IO is performed
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "vendor"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from chunker import chunk_text, CHUNKER_VERSION  # noqa: E402
from extractors import (  # noqa: E402
    DIMENSION_ORDER,
    EXTRACTION_PROMPT_VERSIONS,
    extract_dimension,
)
from extractors import (  # noqa: E402
    dialogue_subtext,
    imagery_rhetoric,
    narrative_voice,
    scene_transition,
    sentence_rhythm,
)
from json_schema_validate import validate as schema_validate  # noqa: E402

CANDIDATE_SCHEMA = json.loads(
    (PROJECT_ROOT / "schemas" / "candidate-mechanism.schema.json").read_text(encoding="utf-8")
)


def _corpus():
    text = (
        "# 第一章 开端\n"
        "句一。句二。\n\n句三。句四。\n\n"
        "# 第二章 发展\n"
        "句五。句六。\n\n句七。句八。\n\n"
        "# 第三章 高潮\n"
        "句九。句十。\n\n句十一。句十二。\n\n"
        "# 第四章 结局\n"
        "句十三。句十四。\n\n句十五。句十六。\n"
    )
    return text, chunk_text(text, chunker_version=CHUNKER_VERSION)


class ExtractorNegativeTests(unittest.TestCase):
    def test_evidence_ref_in_holdout_rejected_by_caller(self):
        text, chunks = _corpus()
        # Mark every chunk as holdout — caller-side filter must produce zero candidates.
        all_ids = {c.chunk_id for c in chunks}
        out = extract_dimension(
            text, chunks, holdout_ids=all_ids, dimension="narrative_voice",
            prompt_version=EXTRACTION_PROMPT_VERSIONS["narrative_voice"],
            profile="all_supported",
        )
        self.assertEqual(out, [])

    def test_dimension_not_in_enum_rejected(self):
        text, chunks = _corpus()
        with self.assertRaises(ValueError):
            extract_dimension(
                text, chunks, holdout_ids=set(),
                dimension="lexical_density",
                prompt_version="lexical_density@0.1.0",
            )


class ExtractorHappyPathTests(unittest.TestCase):
    def test_each_dimension_produces_schema_valid_candidate(self):
        text, chunks = _corpus()
        for dim in DIMENSION_ORDER:
            out = extract_dimension(
                text, chunks, holdout_ids=set(), dimension=dim,
                prompt_version=EXTRACTION_PROMPT_VERSIONS[dim],
                profile="all_supported",
            )
            self.assertGreater(len(out), 0, f"{dim} produced no candidates")
            for candidate in out:
                errors = schema_validate(candidate, CANDIDATE_SCHEMA)
                self.assertEqual(errors, [], f"{dim} candidate schema errors: {errors}")

    def test_dimension_module_exports_extract(self):
        text, chunks = _corpus()
        for module in (
            narrative_voice,
            sentence_rhythm,
            scene_transition,
            dialogue_subtext,
            imagery_rhetoric,
        ):
            self.assertTrue(hasattr(module, "extract"))
            self.assertTrue(hasattr(module, "PROMPT_VERSION"))
            out = module.extract(
                text, chunks, holdout_ids=set(),
                profile="all_supported",
            )
            self.assertGreater(len(out), 0)


class StubHasNoNetworkIOTests(unittest.TestCase):
    def test_stub_does_not_use_socket(self):
        from extractors.base import _stub_model_call
        import extractors.base as base_module

        original_socket = socket.socket
        called = {"value": False}

        def trap_socket(*args, **kwargs):
            called["value"] = True
            raise RuntimeError("socket used")

        text, chunks = _corpus()
        base_module.socket = trap_socket  # type: ignore[assignment]
        try:
            try:
                _stub_model_call("prompt", {
                    "dimension": "narrative_voice",
                    "chunks": chunks,
                    "normalized_text": text,
                    "chunker_version": CHUNKER_VERSION,
                    "extraction_prompt_version": EXTRACTION_PROMPT_VERSIONS["narrative_voice"],
                    "profile": "all_supported",
                })
            except RuntimeError:
                pass
            self.assertFalse(called["value"], "stub must not touch socket.socket")
        finally:
            base_module.socket = original_socket  # type: ignore[assignment]


class StageBindingsTests(unittest.TestCase):
    def test_stage_bindings_within_six_stage_enum(self):
        text, chunks = _corpus()
        out = extract_dimension(
            text, chunks, holdout_ids=set(),
            dimension="narrative_voice",
            prompt_version=EXTRACTION_PROMPT_VERSIONS["narrative_voice"],
            profile="all_supported",
        )
        valid_stages = {
            "write_entry", "scene_design", "character_beats",
            "prose_draft", "style_check", "revision",
        }
        for candidate in out:
            for binding in candidate["stage_bindings"]:
                self.assertIn(binding, valid_stages, binding)


if __name__ == "__main__":
    unittest.main()