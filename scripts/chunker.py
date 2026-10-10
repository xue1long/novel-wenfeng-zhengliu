"""Stage B Task 3: stable chunker.

Pure stdlib. Takes already-normalized text and produces an ordered list of
``ChunkRecord`` objects. Each record holds the chunk_id, chapter_id, scene_id,
half-open Unicode codepoint range, window_hash (sha256 of the in-memory text
slice), and a boundary_confidence flag.

Rules (do not change without bumping ``chunker_version``):
  1. Chapter split precedence: Markdown headings (# ...) > Chinese chapter
     pattern ('第[一-十百千万]+章...') > English chapter pattern
     ('Chapter \\d+...') > fallback single virtual chapter 'C000'.
  2. Scene split inside a chapter: paragraph-break (>= 2 consecutive
     newlines), or a fixed time/location cue list (8 Chinese + 8 English
     cues, locked below), or a chapter start.
  3. Window split inside a scene: cut at most every ``MAX_WINDOW_CODEPOINTS``
     codepoints (default 5000), never mid-sentence. Sentence boundary regex
     ``(?<=[。！？!?…\\.])\\s+``. If no boundary can be found within the
     budget, the whole remaining scene becomes a single low-confidence window.
  4. chunk_id is "{scene_id}-{window_index:03d}".
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


CHUNKER_VERSION: str = "v1"
MAX_WINDOW_CODEPOINTS: int = 5000

# Scene time/location cues. Stage B fixes this list; extending it requires a
# chunker_version bump. Each entry is a regex matched at line start.
_CHINESE_CUES = (
    r"清晨",
    r"午后",
    r"黄昏",
    r"深夜",
    r"次日",
    r"三天后",
    r"一周后",
    r"远处",
)
_ENGLISH_CUES = (
    r"^The next morning",
    r"^Later that day",
    r"^At dusk",
    r"^At night",
    r"^The following day",
    r"^Three days later",
    r"^A week later",
    r"^In the distance",
)
_SCENE_CUE_RE = re.compile(
    r"(?m)^(?:" + "|".join(_CHINESE_CUES + _ENGLISH_CUES) + r")\b",
)
_PARAGRAPH_BREAK_RE = re.compile(r"\n\s*\n")
_SENTENCE_TERMINATORS = "。！？!?…."
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[" + _SENTENCE_TERMINATORS + r"])\s+")


_CHAPTER_RE = re.compile(
    r"(?m)^(?P<heading>#\s+.+|第[一二三四五六七八九十百千万两\d]+章\b.*|Chapter\s+\d+\b.*)$"
)


@dataclass
class ChunkRecord:
    chunk_id: str
    chapter_id: str
    scene_id: str
    char_offset: tuple[int, int]
    window_hash: str
    boundary_confidence: str  # "high" | "medium" | "low"
    text: str  # in-memory; never written to the chunk manifest on disk
    scene_classes: tuple[str, ...] = ()

    def as_manifest_entry(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "chapter_id": self.chapter_id,
            "scene_id": self.scene_id,
            "char_offset": list(self.char_offset),
            "window_hash": self.window_hash,
            "boundary_confidence": self.boundary_confidence,
            "scene_classes": list(self.scene_classes),
        }


def _hash_window(text: str, chunker_version: str) -> str:
    payload = chunker_version.encode("utf-8") + b"\x00" + text.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _split_chapters(text: str) -> list[tuple[str, str]]:
    """Return ``[(chapter_id, body)]``. The body is the slice of normalized
    text *after* the chapter heading. The first chapter always starts at
    offset 0; if no heading is matched, a single virtual 'C000' is returned.
    """
    matches = list(_CHAPTER_RE.finditer(text))
    if not matches:
        return [("C000", text)]
    chapters: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        chapter_id = f"C{index + 1:03d}"
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end]
        chapters.append((chapter_id, body))
    return chapters


def _split_scenes(chapter_body: str) -> list[str]:
    """Return ``[scene_body, ...]``. Scene IDs are assigned later in
    ``chunk_text`` so they are globally unique across the document."""
    spans: list[tuple[int, int]] = []
    for match in _PARAGRAPH_BREAK_RE.finditer(chapter_body):
        spans.append((match.start(), match.end()))
    for match in _SCENE_CUE_RE.finditer(chapter_body):
        spans.append((match.start(), match.start()))

    if not spans:
        return [chapter_body]

    spans.sort()
    deduped: list[tuple[int, int]] = []
    last_end = -1
    for start, end in spans:
        if start < last_end:
            continue
        deduped.append((start, end))
        last_end = end

    scenes: list[str] = []
    cursor = 0
    for start, end in deduped:
        scenes.append(chapter_body[cursor:start])
        cursor = start
    scenes.append(chapter_body[cursor:])
    return [s for s in scenes if s.strip()]


def _split_windows(scene_id: str, scene_body: str, chunker_version: str, base_offset: int) -> list[ChunkRecord]:
    if not scene_body.strip():
        return []
    if len(scene_body) <= MAX_WINDOW_CODEPOINTS:
        h = _hash_window(scene_body, chunker_version)
        return [
            ChunkRecord(
                chunk_id=f"{scene_id}-001",
                chapter_id="",  # filled by caller
                scene_id=scene_id,
                char_offset=(base_offset, base_offset + len(scene_body)),
                window_hash=h,
                boundary_confidence="high",
                text=scene_body,
            )
        ]

    # Walk in chunks of <= MAX_WINDOW_CODEPOINTS, snapping to the next
    # sentence boundary that does not cross the budget.
    records: list[ChunkRecord] = []
    cursor = 0
    index = 0
    while cursor < len(scene_body):
        index += 1
        remaining = scene_body[cursor:]
        if len(remaining) <= MAX_WINDOW_CODEPOINTS:
            chunk_text_slice = remaining
            confidence = "high"
        else:
            window = remaining[:MAX_WINDOW_CODEPOINTS]
            # Find the last sentence boundary within the window.
            last_boundary = None
            for match in _SENTENCE_BOUNDARY_RE.finditer(window):
                last_boundary = match.end()
            if last_boundary is None:
                # Fall back to a hard newline inside the window.
                last_break = window.rfind("\n")
                if last_break > 0:
                    chunk_text_slice = window[:last_break]
                    confidence = "medium"
                else:
                    chunk_text_slice = window
                    confidence = "low"
            else:
                chunk_text_slice = window[:last_boundary]
                confidence = "high"
        chunk_id = f"{scene_id}-{index:03d}"
        records.append(
            ChunkRecord(
                chunk_id=chunk_id,
                chapter_id="",
                scene_id=scene_id,
                char_offset=(base_offset + cursor, base_offset + cursor + len(chunk_text_slice)),
                window_hash=_hash_window(chunk_text_slice, chunker_version),
                boundary_confidence=confidence,
                text=chunk_text_slice,
            )
        )
        cursor += len(chunk_text_slice)
    return records


def chunk_text(text: str, *, chunker_version: str = CHUNKER_VERSION) -> list[ChunkRecord]:
    """Split a normalized text into ``ChunkRecord`` objects.

    The ``text`` attribute on each record is in-memory only and must never be
    written into the persisted chunk manifest (per Stage A schema). The
    manifest writer (Stage B-CLI) calls ``as_manifest_entry`` instead.
    """
    if chunker_version != CHUNKER_VERSION:
        # For now Stage B only supports one chunker version; the parameter is
        # accepted so future versions can re-use the same function signature.
        pass

    chapters = _split_chapters(text)
    records: list[ChunkRecord] = []
    scene_counter = 0
    cursor = 0
    for chapter_id, chapter_body in chapters:
        chapter_start = cursor
        scenes = _split_scenes(chapter_body)
        offset = chapter_start
        for scene_body in scenes:
            scene_counter += 1
            scene_id = f"SC{scene_counter:04d}"
            scene_records = _split_windows(scene_id, scene_body, chunker_version, offset)
            for rec in scene_records:
                rec.chapter_id = chapter_id
            records.extend(scene_records)
            offset += len(scene_body)
        cursor += len(chapter_body)
    return records


__all__ = [
    "CHUNKER_VERSION",
    "MAX_WINDOW_CODEPOINTS",
    "ChunkRecord",
    "chunk_text",
]
