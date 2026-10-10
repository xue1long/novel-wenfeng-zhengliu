"""Stage D Task 1: frontmatter parser + body-section validator for six Skill templates.

Pure stdlib. No PyYAML dependency (Ruling-D7). The parser supports a tiny
YAML subset sufficient for our frontmatter:
  - top-level scalars and one-level mappings (no nesting)
  - flow-style sequences (``[a, b, c]``)
  - flow-style mappings (``{key: value, key2: value2}``)
  - block-style lists with ``- item`` lines
  - ``#`` comments

Anything more exotic (anchors, multi-doc, tags) is intentionally rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


SIX_STAGE_IDS: tuple[str, ...] = (
    "write_entry",
    "scene_design",
    "character_beats",
    "prose_draft",
    "style_check",
    "revision",
)

REQUIRED_FRONTMATTER_FIELDS: tuple[str, ...] = (
    "name",
    "description",
    "stage_id",
    "contract_version",
    "trigger_examples",
    "required_inputs",
    "primary_output",
    "missing_input_behavior",
    "stop_conditions",
    "not_allowed",
)

REQUIRED_BODY_SECTIONS: tuple[str, ...] = (
    "触发条件",
    "必读输入",
    "主要输出",
    "缺失输入行为",
    "停止条件",
    "不做事项",
)


class TemplateParseError(Exception):
    def __init__(self, message: str, *, error_type: str = "template_parse_error") -> None:
        super().__init__(message)
        self.error_type = error_type


@dataclass
class ParsedTemplate:
    path: Path
    frontmatter: dict
    body: str
    sections: list[str] = field(default_factory=list)


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


def _strip_inline_comment(line: str) -> str:
    in_str = False
    quote = ""
    for index, char in enumerate(line):
        if char in ("'", '"') and (index == 0 or line[index - 1] != "\\"):
            if in_str and char == quote:
                in_str = False
            elif not in_str:
                in_str = True
                quote = char
        elif char == "#" and not in_str:
            return line[:index].rstrip()
    return line.rstrip()


def _parse_flow_sequence(text: str) -> list:
    """Parse a flow-style sequence into strings.

    Stage D entries are short and never contain top-level commas. Dotted keys
    (``a.b.c``) are kept as strings so ``required_inputs`` is a list of
    strings, not a list of one-key mappings.
    """
    inner = text.strip()[1:-1].strip()
    if not inner:
        return []
    return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]


def _parse_flow_mapping(text: str) -> dict:
    inner = text.strip()[1:-1].strip()
    if not inner:
        return {}
    out: dict = {}
    # Split on top-level commas only. Our templates never have nested commas in
    # values, so a plain split is sufficient and unambiguous for Stage D.
    parts = [p.strip() for p in inner.split(",") if p.strip()]
    for part in parts:
        if ":" not in part:
            raise TemplateParseError(f"flow mapping entry missing ':': {part!r}")
        key, _, value = part.partition(":")
        key = key.strip().strip("'\"")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            out[key] = _parse_flow_sequence(value)
        elif value.startswith("{") and value.endswith("}") and _looks_like_flow_mapping(value):
            out[key] = _parse_flow_mapping(value)
        elif value.lower() in ("true", "false"):
            out[key] = value.lower() == "true"
        else:
            out[key] = value.strip("'\"")
    return out


def _looks_like_flow_mapping(text: str) -> bool:
    """A ``{...}`` token is a flow mapping iff it contains at least one
    ``key: value`` pair (possibly with nested flow forms). A lone identifier
    like ``{placeholder}`` is a placeholder, not a mapping.
    """
    inner = text.strip()[1:-1].strip()
    if not inner:
        return False
    parts = [p.strip() for p in inner.split(",") if p.strip()]
    return any(":" in part for part in parts)


def _parse_frontmatter(raw: str) -> dict:
    """Parse the YAML subset we use. Raises TemplateParseError on unknown shapes."""
    out: dict = {}
    lines = raw.splitlines()
    index = 0
    while index < len(lines):
        original = lines[index]
        stripped = _strip_inline_comment(original)
        if not stripped.strip():
            index += 1
            continue
        # Block list entries ``- item`` attach to the most recent mapping key.
        if stripped.lstrip().startswith("- "):
            indent = len(stripped) - len(stripped.lstrip())
            if not out:
                raise TemplateParseError(f"orphan list item: {original!r}")
            key = next(reversed(list(out.keys())))
            if not isinstance(out[key], list):
                out[key] = []
            value = stripped.lstrip()[2:].strip()
            if value.startswith("[") and value.endswith("]"):
                out[key].extend(_parse_flow_sequence(value))
            else:
                out[key].append(value.strip("'\""))
            index += 1
            continue
        if ":" not in stripped:
            raise TemplateParseError(f"expected key:value at line {index + 1}: {original!r}")
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "" or value in ("|", ">"):
            # Multi-line block. The next indented block could be:
            #   - a sub-mapping (``subkey:`` or ``subkey: value``)
            #   - a list (``- item``)
            #   - a literal/folded scalar (``|`` / ``>``)
            index += 1
            indent_of_key = len(original) - len(original.lstrip())
            if value == "":
                sub_lines: list[str] = []
                while index < len(lines):
                    nxt = lines[index]
                    if nxt.strip() == "":
                        sub_lines.append("")
                        index += 1
                        continue
                    nxt_indent = len(nxt) - len(nxt.lstrip())
                    if nxt_indent <= indent_of_key:
                        break
                    sub_lines.append(nxt)
                    index += 1
                non_empty = [line for line in sub_lines if line.strip()]
                if non_empty and non_empty[0].lstrip().startswith("- "):
                    out[key] = _parse_block_list(sub_lines, indent_of_key)
                elif non_empty and ":" in non_empty[0].lstrip():
                    out[key] = _parse_block_mapping(sub_lines, indent_of_key)
                else:
                    out[key] = "\n".join(line.strip() for line in sub_lines).strip()
                continue
            # value == "|" or ">": block scalar.
            block_lines: list[str] = []
            while index < len(lines):
                nxt = lines[index]
                if nxt.strip() == "":
                    block_lines.append("")
                    index += 1
                    continue
                nxt_indent = len(nxt) - len(nxt.lstrip())
                if nxt_indent <= indent_of_key:
                    break
                block_lines.append(nxt.strip())
                index += 1
            value = "\n".join(block_lines).strip()
            out[key] = value
            continue
        if value.startswith("[") and value.endswith("]"):
            out[key] = _parse_flow_sequence(value)
        elif value.startswith("{") and value.endswith("}") and _looks_like_flow_mapping(value):
            out[key] = _parse_flow_mapping(value)
        elif value.lower() in ("true", "false"):
            out[key] = value.lower() == "true"
        else:
            out[key] = value.strip("'\"")
        index += 1
    return out


def _parse_block_list(lines: list[str], base_indent: int) -> list:
    """Parse a block-style list whose first ``- item`` is at ``base_indent + 2``.

    Items are strings unless they start with ``{key: value}`` style mapping,
    in which case they are returned as one-key mappings.
    """
    out: list = []
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            continue
        if not stripped_line.startswith("- "):
            raise TemplateParseError(f"expected list item, got: {stripped_line!r}")
        value = stripped_line[2:].strip()
        if value.startswith("[") and value.endswith("]"):
            out.extend(_parse_flow_sequence(value))
        elif value.startswith("{") and value.endswith("}"):
            out.append(_parse_flow_mapping(value))
        else:
            out.append(value.strip("'\""))
    return out


def _parse_block_mapping(lines: list[str], base_indent: int) -> dict:
    """Parse a block-style mapping with optional nested blocks."""
    out: dict = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if ":" not in stripped:
            raise TemplateParseError(f"expected mapping entry, got: {stripped!r}")
        sub_key, _, sub_value = stripped.partition(":")
        sub_key = sub_key.strip()
        sub_value = sub_value.strip()
        key_indent = len(line) - len(line.lstrip())
        if sub_value == "":
            sub_lines: list[str] = []
            index += 1
            while index < len(lines):
                nxt = lines[index]
                if nxt.strip() == "":
                    sub_lines.append("")
                    index += 1
                    continue
                nxt_indent = len(nxt) - len(nxt.lstrip())
                if nxt_indent <= key_indent:
                    break
                sub_lines.append(nxt)
                index += 1
            if sub_lines and any(line.lstrip().startswith("- ") for line in sub_lines if line.strip()):
                out[sub_key] = _parse_block_list(sub_lines, key_indent)
            else:
                out[sub_key] = "\n".join(line.strip() for line in sub_lines).strip()
            continue
        if sub_value.startswith("[") and sub_value.endswith("]"):
            out[sub_key] = _parse_flow_sequence(sub_value)
        elif sub_value.startswith("{") and sub_value.endswith("}"):
            out[sub_key] = _parse_flow_mapping(sub_value)
        else:
            out[sub_key] = sub_value.strip("'\"")
        index += 1
    return out


def _extract_body_sections(body: str) -> list[str]:
    """Return the H2 headings (text only) in the order they appear."""
    return [
        match.group(1).strip()
        for match in re.finditer(r"(?m)^##\s+(.+?)\s*$", body)
    ]


def parse_template(path: Path) -> ParsedTemplate:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise TemplateParseError(f"{path.name}: missing YAML frontmatter (--- delimiter)")
    frontmatter = _parse_frontmatter(match.group(1))
    body = match.group(2)
    sections = _extract_body_sections(body)

    for field in REQUIRED_FRONTMATTER_FIELDS:
        if field not in frontmatter:
            raise TemplateParseError(
                f"{path.name}: frontmatter missing required field {field!r}"
            )

    stage_id = frontmatter.get("stage_id")
    if stage_id not in SIX_STAGE_IDS:
        raise TemplateParseError(
            f"{path.name}: stage_id {stage_id!r} not in six-stage enum"
        )
    if frontmatter.get("name") != stage_id:
        raise TemplateParseError(
            f"{path.name}: name {frontmatter.get('name')!r} must equal stage_id {stage_id!r}"
        )

    trigger_examples = frontmatter.get("trigger_examples")
    if not isinstance(trigger_examples, dict):
        raise TemplateParseError(
            f"{path.name}: trigger_examples must be a mapping with positive/negative"
        )
    positive = trigger_examples.get("positive") or []
    negative = trigger_examples.get("negative") or []
    if len(positive) < 1 or len(negative) < 1:
        raise TemplateParseError(
            f"{path.name}: trigger_examples must have >=1 positive and >=1 negative example"
        )

    missing_sections = [s for s in REQUIRED_BODY_SECTIONS if s not in sections]
    if missing_sections:
        raise TemplateParseError(
            f"{path.name}: body missing required H2 sections: {missing_sections}"
        )

    return ParsedTemplate(path=path, frontmatter=frontmatter, body=body, sections=sections)


def list_stage_templates(root: Path) -> list[Path]:
    if not root.is_dir():
        raise FileNotFoundError(f"templates root missing: {root}")
    return sorted(p for p in root.glob("*.md") if p.is_file())


__all__ = [
    "SIX_STAGE_IDS",
    "REQUIRED_FRONTMATTER_FIELDS",
    "REQUIRED_BODY_SECTIONS",
    "TemplateParseError",
    "ParsedTemplate",
    "parse_template",
    "list_stage_templates",
]