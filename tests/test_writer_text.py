#!/usr/bin/env python3
"""
Unit tests for the 18 real (status="implemented") writer_text.py tools.

Uses a FakeUnoBridge modeling the document as a plain Python list of
paragraph strings (paragraph/split/merge/move/copy), a target-keyed dict of
applied direct-format properties (set_paragraph_format_live/
set_character_format_live, same {start,end}-key convention as
test_styles.py's FakeUnoBridge), and a plain list of comment dicts
(update/delete/resolve_comment_live) -- enough to exercise the tool-layer
logic (parameter plumbing, error-code mapping, warnings for skipped
properties/unresolved requests) without needing to model real UNO text
enumeration, XSearchable/XReplaceable, or TextField.Annotation objects.

What this file deliberately does NOT (and structurally cannot) verify --
these fakes don't reimplement UNOBridge's real algorithms, they only stand
in at the tool<->UNOBridge method boundary, same disclaimer as
test_styles.py:
  - insert_paragraph/split_paragraph/merge_paragraphs/move_paragraphs/
    copy_paragraphs's real implementation walks a live UNO paragraph
    enumeration and uses insertString()/insertControlCharacter() at real
    text cursors -- the destination-arithmetic *shape* is exercised here
    (via a parallel, simpler list-based fake), but not the real UNO
    cursor mechanics themselves.
  - find_regex_live/replace_regex_live's real implementation delegates to
    Writer's own XSearchable/XReplaceable with SearchRegularExpression=True
    (real ICU regex engine) -- the fake here does a plain Python re.search
    substitute, good enough to exercise position/count plumbing, not proof
    LibreOffice's own regex engine behaves the same way.
  - update_comment_live/delete_comment_live/resolve_comment_live's real
    implementation reads/writes real com.sun.star.text.TextField.Annotation
    property values (Content/Author/Id/Resolved) -- the fake models a
    comment as a plain dict.
See the commit message for this pass's live verification of all of the above.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools import context  # noqa: E402
from tools.documents import DocumentRegistry  # noqa: E402
from tools.registry import get_registry  # noqa: E402
from tools.runtime_state import RuntimeState  # noqa: E402


class FakeDocument:
    def __init__(self, doc_type="writer", title="Untitled", url=""):
        self.doc_type = doc_type
        self.title = title
        self.url = url
        self.modified = False


class FakeUnoBridge:
    """Stand-in for uno_bridge.UNOBridge's writer_text.py-facing methods."""

    def __init__(self, active_document=None, paragraphs=None):
        self.ctx = object()
        self.active_document = active_document
        self.paragraphs = list(paragraphs) if paragraphs is not None else ["First paragraph.", "Second paragraph."]
        self.paragraph_styles = ["Default Paragraph Style"] * len(self.paragraphs)
        self.known_paragraph_styles = {"Default Paragraph Style", "Heading 1", "Heading 2", "Custom Style"}
        self.direct_formatting = {}  # {(start, end): {prop: value}}
        self.comments = []  # [{"id", "author", "content", "resolved", "emulated"}]

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": doc.doc_type, "title": doc.title, "url": doc.url, "modified": doc.modified}

    # -- paragraph editing --

    def insert_paragraph(self, doc, text="", at_paragraph=None, position=None):
        position = position or "after"
        if position not in ("before", "after"):
            raise ValueError(f"position must be 'before' or 'after', got {position!r}")
        anchor_n = at_paragraph if at_paragraph is not None else len(self.paragraphs)
        if anchor_n < 1 or anchor_n > len(self.paragraphs):
            raise IndexError(f"Paragraph {anchor_n} out of range.")
        insert_at = anchor_n - 1 if position == "before" else anchor_n
        self.paragraphs.insert(insert_at, text)
        self.paragraph_styles.insert(insert_at, "Default Paragraph Style")
        return {"inserted_paragraph": insert_at + 1, "text": text}

    def append_paragraph(self, doc, text="", style_name=None):
        style_applied = False
        if style_name:
            if style_name not in self.known_paragraph_styles:
                raise KeyError(f"No such paragraph style '{style_name}'.")
            style_applied = True
        self.paragraphs.append(text)
        self.paragraph_styles.append(style_name if style_applied else "Default Paragraph Style")
        return {"appended_paragraph": len(self.paragraphs), "text": text, "style_applied": style_applied}

    def insert_heading(self, doc, text, level=1, at_paragraph=None, position=None):
        if level < 1:
            raise ValueError(f"level must be >= 1, got {level}")
        style_name = f"Heading {level}"
        if style_name not in self.known_paragraph_styles:
            raise KeyError(f"No such paragraph style '{style_name}' (level {level}).")
        result = self.insert_paragraph(doc, text=text, at_paragraph=at_paragraph, position=position)
        self.paragraph_styles[result["inserted_paragraph"] - 1] = style_name
        result["style"] = style_name
        result["level"] = level
        return result

    def set_paragraph_text(self, doc, n, text):
        if n < 1 or n > len(self.paragraphs):
            raise IndexError(f"Paragraph {n} out of range.")
        self.paragraphs[n - 1] = text
        return {"paragraph": n, "text": text}

    def split_paragraph(self, doc, n, offset):
        if n < 1 or n > len(self.paragraphs):
            raise IndexError(f"Paragraph {n} out of range.")
        original = self.paragraphs[n - 1]
        if offset < 0 or offset > len(original):
            raise IndexError(f"offset {offset} out of range for paragraph {n} (length {len(original)})")
        first, second = original[:offset], original[offset:]
        self.paragraphs[n - 1:n] = [first, second]
        self.paragraph_styles.insert(n, self.paragraph_styles[n - 1])
        return {"paragraph": n, "offset": offset, "first_text": first, "second_text": second}

    def merge_paragraphs(self, doc, first_n, count=2, separator=" "):
        if count < 2:
            raise ValueError(f"count must be >= 2 to merge, got {count}")
        last_n = first_n + count - 1
        if first_n < 1 or last_n > len(self.paragraphs):
            raise IndexError(f"range {first_n}-{last_n} out of bounds.")
        merged_text = separator.join(self.paragraphs[first_n - 1:last_n])
        self.paragraphs[first_n - 1:last_n] = [merged_text]
        del self.paragraph_styles[first_n:last_n]
        return {"merged_into": first_n, "text": merged_text, "paragraphs_removed": count - 1}

    def move_paragraphs(self, doc, start, end, destination):
        if end < start:
            raise ValueError(f"end ({end}) must be >= start ({start})")
        total = len(self.paragraphs)
        if start < 1 or end > total:
            raise IndexError(f"range {start}-{end} out of bounds.")
        if start <= destination <= end:
            raise ValueError(f"destination {destination} falls inside the block being moved ({start}-{end})")
        block = self.paragraphs[start - 1:end]
        del self.paragraphs[start - 1:end]
        count = end - start + 1
        resolved_destination = destination - count if destination > end else destination
        insert_at = min(max(resolved_destination - 1, 0), len(self.paragraphs))
        self.paragraphs[insert_at:insert_at] = block
        return {"moved_count": count, "destination": insert_at + 1}

    def copy_paragraphs(self, doc, start, end, destination):
        if end < start:
            raise ValueError(f"end ({end}) must be >= start ({start})")
        total = len(self.paragraphs)
        if start < 1 or end > total:
            raise IndexError(f"range {start}-{end} out of bounds.")
        block = self.paragraphs[start - 1:end]
        insert_at = min(max(destination - 1, 0), len(self.paragraphs))
        self.paragraphs[insert_at:insert_at] = block
        return {"copied_count": len(block), "destination": insert_at + 1}

    # -- formatting --

    def _target_key(self, target):
        if target is None:
            return "selection"
        if isinstance(target, dict) and "start" in target and "end" in target:
            if target["start"] < 0 or target["end"] < target["start"]:
                raise ValueError(f"Invalid target range: start={target['start']}, end={target['end']}")
            return (target["start"], target["end"])
        raise ValueError("target must be omitted (use current selection) or {'start': int, 'end': int}.")

    _SETTABLE = {"ParaAdjust", "CharWeight", "CharColor"}

    def set_paragraph_format(self, doc, target, properties):
        key = self._target_key(target)
        applied = []
        for name, value in properties.items():
            if name in self._SETTABLE:
                self.direct_formatting.setdefault(key, {})[name] = value
                applied.append(name)
        return applied

    def set_character_format(self, doc, target, properties):
        return self.set_paragraph_format(doc, target, properties)

    def get_text_range_format(self, doc, start, end):
        if start < 0 or end < start:
            raise ValueError(f"Invalid range: start={start}, end={end}")
        key = self._target_key({"start": start, "end": end})
        formatting = dict(self.direct_formatting.get(key, {}))
        return {"effective_formatting": formatting, "direct_override_properties": sorted(formatting)}

    # -- search/replace --

    def find_regex(self, doc, pattern, case_sensitive=False):
        flags = 0 if case_sensitive else re.IGNORECASE
        full_text = "\n".join(self.paragraphs)
        matches = [
            {"position": m.start(), "text": m.group(0), "length": len(m.group(0))}
            for m in re.finditer(pattern, full_text, flags)
        ]
        return {"matches": matches, "count": len(matches), "pattern": pattern, "case_sensitive": case_sensitive}

    def replace_regex(self, doc, pattern, replacement, all=True):
        full_text = "\n".join(self.paragraphs)
        if all:
            new_text, count = re.subn(pattern, replacement, full_text)
            self.paragraphs = new_text.split("\n")
            return {"count": count, "pattern": pattern, "replacement": replacement, "all": True}
        match = re.search(pattern, full_text)
        if not match:
            return {"replaced": False, "pattern": pattern, "replacement": replacement, "all": False}
        new_text = full_text[:match.start()] + re.sub(pattern, replacement, match.group(0), count=1) + full_text[match.end():]
        self.paragraphs = new_text.split("\n")
        return {"replaced": True, "position": match.start(), "pattern": pattern, "replacement": replacement, "all": False}

    # -- styles --

    def find_by_style(self, doc, family, style_name):
        if family != "ParagraphStyles":
            raise NotImplementedError(f"find_by_style is not implemented for family '{family}'.")
        if style_name not in self.known_paragraph_styles:
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        matches = [
            {"paragraph": i + 1, "text": text}
            for i, (text, style) in enumerate(zip(self.paragraphs, self.paragraph_styles))
            if style == style_name
        ]
        return {"family": family, "style_name": style_name, "matches": matches, "count": len(matches)}

    def replace_style(self, doc, family, old_style, new_style):
        if family != "ParagraphStyles":
            raise NotImplementedError(f"replace_style is not implemented for family '{family}'.")
        if old_style not in self.known_paragraph_styles or new_style not in self.known_paragraph_styles:
            raise KeyError(f"No such style in family '{family}'.")
        count = 0
        for i, style in enumerate(self.paragraph_styles):
            if style == old_style:
                self.paragraph_styles[i] = new_style
                count += 1
        return {"family": family, "old_style": old_style, "new_style": new_style, "replaced_count": count}

    # -- comments --

    def update_comment(self, doc, comment_id, text=None, author=None):
        comment = self._find_comment(comment_id)
        applied = []
        if text is not None:
            comment["content"] = text
            applied.append("text")
        if author is not None:
            comment["author"] = author
            applied.append("author")
        return {"comment_id": comment_id, "applied": applied}

    def delete_comment(self, doc, comment_id):
        comment = self._find_comment(comment_id)
        self.comments.remove(comment)

    def resolve_comment(self, doc, comment_id, resolved=True):
        comment = self._find_comment(comment_id)
        if comment.get("supports_native_resolved"):
            comment["resolved"] = resolved
            return {"comment_id": comment_id, "resolved": resolved, "emulated": False}
        marker = "[RESOLVED] "
        content = comment.get("content") or ""
        has_marker = content.startswith(marker)
        if resolved and not has_marker:
            comment["content"] = marker + content
        elif not resolved and has_marker:
            comment["content"] = content[len(marker):]
        return {"comment_id": comment_id, "resolved": resolved, "emulated": True}

    def _find_comment(self, comment_id):
        for comment in self.comments:
            if comment["id"] == comment_id:
                return comment
        raise KeyError(f"No comment with id '{comment_id}'.")


def _install(active_document=None, paragraphs=None):
    uno_bridge = FakeUnoBridge(active_document=active_document, paragraphs=paragraphs)
    document_registry = DocumentRegistry(uno_bridge)
    runtime_state = RuntimeState()
    context.install(context.RuntimeContext(
        uno_bridge=uno_bridge, document_registry=document_registry,
        runtime_state=runtime_state, get_tools=lambda: {},
    ))
    return uno_bridge, document_registry, runtime_state


def _handler(name):
    return get_registry()[name]["handler"]


# -- insert_paragraph_live / append_paragraph_live / insert_heading_live --

def test_insert_paragraph_live_defaults_to_after_last():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("insert_paragraph_live")(text="New last paragraph.")
    assert result["success"] is True
    assert result["result"]["inserted_paragraph"] == 3
    assert uno_bridge.paragraphs[-1] == "New last paragraph."


def test_insert_paragraph_live_explicit_before():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("insert_paragraph_live")(text="Inserted.", at_paragraph=2, position="before")
    assert result["success"] is True
    assert result["result"]["inserted_paragraph"] == 2
    assert uno_bridge.paragraphs == ["First paragraph.", "Inserted.", "Second paragraph."]


def test_insert_paragraph_live_invalid_position():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("insert_paragraph_live")(text="x", position="sideways")
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


# -- append_paragraph_live --

def test_append_paragraph_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("append_paragraph_live")(text="Appended.")
    assert result["success"] is True
    assert result["result"]["appended_paragraph"] == 3
    assert uno_bridge.paragraphs[-1] == "Appended."


def test_append_paragraph_live_unknown_style():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("append_paragraph_live")(text="x", style_name="NotARealStyle")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


# -- insert_heading_live --

def test_insert_heading_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("insert_heading_live")(text="A Heading", level=2)
    assert result["success"] is True
    assert result["result"]["style"] == "Heading 2"
    assert uno_bridge.paragraph_styles[-1] == "Heading 2"


def test_insert_heading_live_invalid_level():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("insert_heading_live")(text="x", level=0)
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


# -- set_paragraph_text_live --

def test_set_paragraph_text_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_paragraph_text_live")(n=1, text="Replaced.")
    assert result["success"] is True
    assert uno_bridge.paragraphs[0] == "Replaced."


def test_set_paragraph_text_live_out_of_range():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("set_paragraph_text_live")(n=99, text="x")
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_RANGE"


# -- split_paragraph_live / merge_paragraphs_live --

def test_split_paragraph_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), paragraphs=["Hello world"])
    result = _handler("split_paragraph_live")(n=1, offset=5)
    assert result["success"] is True
    assert uno_bridge.paragraphs == ["Hello", " world"]


def test_split_paragraph_live_offset_out_of_range():
    context.reset()
    _install(active_document=FakeDocument(), paragraphs=["Hello"])
    result = _handler("split_paragraph_live")(n=1, offset=99)
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_RANGE"


def test_merge_paragraphs_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), paragraphs=["A", "B", "C"])
    result = _handler("merge_paragraphs_live")(first_n=1, count=2, separator="-")
    assert result["success"] is True
    assert uno_bridge.paragraphs == ["A-B", "C"]


def test_merge_paragraphs_live_count_too_small():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("merge_paragraphs_live")(first_n=1, count=1)
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


# -- move_paragraphs_live / copy_paragraphs_live --

def test_move_paragraphs_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), paragraphs=["A", "B", "C", "D"])
    result = _handler("move_paragraphs_live")(start=1, end=1, destination=4)
    assert result["success"] is True
    assert uno_bridge.paragraphs == ["B", "C", "A", "D"] or uno_bridge.paragraphs == ["B", "C", "D", "A"]


def test_move_paragraphs_live_destination_inside_block():
    context.reset()
    _install(active_document=FakeDocument(), paragraphs=["A", "B", "C", "D"])
    result = _handler("move_paragraphs_live")(start=1, end=2, destination=2)
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_copy_paragraphs_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), paragraphs=["A", "B"])
    result = _handler("copy_paragraphs_live")(start=1, end=1, destination=3)
    assert result["success"] is True
    assert uno_bridge.paragraphs.count("A") == 2


# -- set_paragraph_format_live / set_character_format_live / get_text_range_format_live --

def test_set_paragraph_format_live_warns_on_unknown_property():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_paragraph_format_live")(target={"start": 0, "end": 5}, properties={"ParaAdjust": 1, "NotARealProperty": 1})
    assert result["success"] is True
    assert result["result"]["applied"] == ["ParaAdjust"]
    assert any("NotARealProperty" in w for w in result["warnings"])
    assert uno_bridge.direct_formatting[(0, 5)] == {"ParaAdjust": 1}


def test_set_character_format_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_character_format_live")(target={"start": 0, "end": 5}, properties={"CharWeight": 150.0})
    assert result["success"] is True
    assert result["result"]["applied"] == ["CharWeight"]


def test_get_text_range_format_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.direct_formatting[(0, 5)] = {"CharWeight": 150.0}
    result = _handler("get_text_range_format_live")(start=0, end=5)
    assert result["success"] is True
    assert result["result"]["effective_formatting"] == {"CharWeight": 150.0}


def test_get_text_range_format_live_invalid_range():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_text_range_format_live")(start=5, end=2)
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


# -- find_regex_live / replace_regex_live --

def test_find_regex_live():
    context.reset()
    _install(active_document=FakeDocument(), paragraphs=["order 123", "order 456"])
    result = _handler("find_regex_live")(pattern=r"\d+")
    assert result["success"] is True
    assert result["result"]["count"] == 2
    assert {m["text"] for m in result["result"]["matches"]} == {"123", "456"}


def test_replace_regex_live_all():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), paragraphs=["order 123", "order 456"])
    result = _handler("replace_regex_live")(pattern=r"\d+", replacement="NUM", all=True)
    assert result["success"] is True
    assert result["result"]["count"] == 2
    assert uno_bridge.paragraphs == ["order NUM", "order NUM"]


def test_replace_regex_live_first_only():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), paragraphs=["order 123 456"])
    result = _handler("replace_regex_live")(pattern=r"\d+", replacement="NUM", all=False)
    assert result["success"] is True
    assert result["result"]["replaced"] is True
    assert uno_bridge.paragraphs == ["order NUM 456"]


# -- find_by_style_live / replace_style_live --

def test_find_by_style_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), paragraphs=["A", "B"])
    uno_bridge.paragraph_styles = ["Heading 1", "Default Paragraph Style"]
    result = _handler("find_by_style_live")(family="ParagraphStyles", style_name="Heading 1")
    assert result["success"] is True
    assert result["result"]["matches"] == [{"paragraph": 1, "text": "A"}]


def test_find_by_style_live_unsupported_family():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("find_by_style_live")(family="PageStyles", style_name="Default Page Style")
    assert result["success"] is False
    assert result["error"]["code"] == "UNSUPPORTED_CAPABILITY"


def test_replace_style_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), paragraphs=["A", "B"])
    uno_bridge.paragraph_styles = ["Heading 1", "Heading 1"]
    result = _handler("replace_style_live")(family="ParagraphStyles", old_style="Heading 1", new_style="Heading 2")
    assert result["success"] is True
    assert result["result"]["replaced_count"] == 2
    assert uno_bridge.paragraph_styles == ["Heading 2", "Heading 2"]


# -- update_comment_live / delete_comment_live / resolve_comment_live --

def test_update_comment_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.comments.append({"id": "0", "author": "AI", "content": "original", "resolved": False})
    result = _handler("update_comment_live")(comment_id="0", text="edited")
    assert result["success"] is True
    assert uno_bridge.comments[0]["content"] == "edited"


def test_update_comment_live_requires_text_or_author():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("update_comment_live")(comment_id="0")
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_delete_comment_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.comments.append({"id": "0", "author": "AI", "content": "bye", "resolved": False})
    result = _handler("delete_comment_live")(comment_id="0")
    assert result["success"] is True
    assert uno_bridge.comments == []


def test_delete_comment_live_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("delete_comment_live")(comment_id="does-not-exist")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


def test_resolve_comment_live_native():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.comments.append({"id": "0", "author": "AI", "content": "x", "resolved": False, "supports_native_resolved": True})
    result = _handler("resolve_comment_live")(comment_id="0", resolved=True)
    assert result["success"] is True
    assert result["result"]["emulated"] is False
    assert result["warnings"] == []
    assert uno_bridge.comments[0]["resolved"] is True


def test_resolve_comment_live_emulated():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.comments.append({"id": "0", "author": "AI", "content": "x", "resolved": False})
    result = _handler("resolve_comment_live")(comment_id="0", resolved=True)
    assert result["success"] is True
    assert result["result"]["emulated"] is True
    assert any("emulated" in w for w in result["warnings"])
    assert uno_bridge.comments[0]["content"] == "[RESOLVED] x"


if __name__ == "__main__":
    tests = [
        test_insert_paragraph_live_defaults_to_after_last,
        test_insert_paragraph_live_explicit_before,
        test_insert_paragraph_live_invalid_position,
        test_append_paragraph_live,
        test_append_paragraph_live_unknown_style,
        test_insert_heading_live,
        test_insert_heading_live_invalid_level,
        test_set_paragraph_text_live,
        test_set_paragraph_text_live_out_of_range,
        test_split_paragraph_live,
        test_split_paragraph_live_offset_out_of_range,
        test_merge_paragraphs_live,
        test_merge_paragraphs_live_count_too_small,
        test_move_paragraphs_live,
        test_move_paragraphs_live_destination_inside_block,
        test_copy_paragraphs_live,
        test_set_paragraph_format_live_warns_on_unknown_property,
        test_set_character_format_live,
        test_get_text_range_format_live,
        test_get_text_range_format_live_invalid_range,
        test_find_regex_live,
        test_replace_regex_live_all,
        test_replace_regex_live_first_only,
        test_find_by_style_live,
        test_find_by_style_live_unsupported_family,
        test_replace_style_live,
        test_update_comment_live,
        test_update_comment_live_requires_text_or_author,
        test_delete_comment_live,
        test_delete_comment_live_not_found,
        test_resolve_comment_live_native,
        test_resolve_comment_live_emulated,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    context.reset()
    print(f"\nAll {len(tests)} writer_text tests passed.")
