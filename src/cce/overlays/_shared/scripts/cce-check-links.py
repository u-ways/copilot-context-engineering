#!/usr/bin/env python3
"""Validate inline Markdown links in a repository checkout.

This script is shipped into scenario worktrees and run with whatever ``python3``
the user has, so it depends on the standard library only and stays compatible
with Python 3.9. It reports three classes of problem and never fetches anything:

- missing relative targets: the linked path does not exist on disk;
- unresolved fragments: ``#fragment`` names no heading slug or HTML anchor in
  the target Markdown file;
- email targets without ``mailto:``: a bare address used as a link target.

Usage: ``python3 cce-check-links.py [ROOT]`` (ROOT defaults to the current
directory). The exit code is 1 when any finding is reported, otherwise 0.
"""

from __future__ import annotations

import argparse
import html
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

SKIPPED_DIRECTORIES = frozenset({".git", ".github", ".claude"})
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "ftp://")
MARKDOWN_SUFFIXES = frozenset({".md", ".markdown"})

LABEL_MISSING = "missing relative targets"
LABEL_FRAGMENTS = "unresolved fragments"
LABEL_EMAIL = "email targets without mailto:"

# ``[text](target)`` or ``![alt](target)``; the text may hold one level of
# nested brackets so that badge links (an image inside a link) are found. The
# target is either ``<angled>`` or a bare run without whitespace that may hold
# one level of balanced parentheses; an optional quoted title follows.
_LINK_RE = re.compile(
    r"!?\[(?P<text>(?:[^\[\]]|\[[^\[\]]*\])*)\]"
    r"\(\s*(?:<(?P<angled>[^>]*)>|(?P<bare>[^\s()]*(?:\([^\s()]*\)[^\s()]*)*))"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)"
)
_CODE_SPAN_RE = re.compile(r"(`+).*?\1")
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_HEADING_RE = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+(?P<text>.*?))?(?:[ \t]+#+)?[ \t]*$")
_ANCHOR_NAME_RE = re.compile(r"<a\b[^>]*\bname\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)
_ANCHOR_ID_RE = re.compile(r"\bid\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[^\s@/]+@[^\s@/]+\.[^\s@/]+$")

# Slug helpers: inline markup is stripped before GitHub's character filter.
_IMAGE_MARKUP_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_MARKUP_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_REFERENCE_MARKUP_RE = re.compile(r"\[([^\]]*)\]\[[^\]]*\]")
_STAR_EMPHASIS_RE = re.compile(r"(\*{1,3})(?=\S)(.+?)(?<=\S)\1")
_UNDERSCORE_EMPHASIS_RE = re.compile(r"(?<!\w)(_{1,3})(?=\S)(.+?)(?<=\S)\1(?!\w)")
_SLUG_DROP_RE = re.compile(r"[^\w\- ]")


@dataclass(frozen=True)
class Link:
    """One inline link found in a Markdown file."""

    file: Path
    line: int
    target: str


@dataclass(frozen=True)
class Finding:
    """A reported problem, printed as ``file:line -> target``."""

    file: str
    line: int
    target: str

    def render(self) -> str:
        return f"  {self.file}:{self.line} -> {self.target}"


@dataclass
class Report:
    """Everything the validator prints."""

    files: int = 0
    links: int = 0
    external: int = 0
    relative: int = 0
    fragments: int = 0
    missing: list[Finding] = field(default_factory=list)
    unresolved: list[Finding] = field(default_factory=list)
    email: list[Finding] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return bool(self.missing or self.unresolved or self.email)

    def render(self) -> str:
        lines = [
            f"scanned {self.files} markdown files, {self.links} inline links "
            f"({self.external} external, {self.relative} relative paths, "
            f"{self.fragments} fragments)"
        ]
        for label, findings in (
            (LABEL_MISSING, self.missing),
            (LABEL_FRAGMENTS, self.unresolved),
            (LABEL_EMAIL, self.email),
        ):
            lines.append(f"{label} : {len(findings)}")
            lines.extend(finding.render() for finding in findings)
        lines.append("RESULT: FAIL" if self.failed else "RESULT: PASS")
        return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(
        prog="cce-check-links.py",
        description="Validate inline Markdown links under ROOT without touching the network.",
    )
    parser.add_argument("root", nargs="?", default=".", help="directory to scan (default: .)")
    options = parser.parse_args(argv)
    root = Path(options.root)
    if not root.is_dir():
        parser.error(f"not a directory: {options.root}")
    report = check(root)
    print(report.render())
    return 1 if report.failed else 0


def check(root: Path) -> Report:
    """Scan every Markdown file under ``root`` and build the report."""
    root = root.resolve()
    report = Report()
    anchors: dict[Path, frozenset[str]] = {}
    for file in markdown_files(root):
        report.files += 1
        for link in iter_links(file):
            report.links += 1
            _classify(link, root, report, anchors)
    return report


def markdown_files(root: Path) -> list[Path]:
    """Every ``*.md`` file under ``root``, sorted, skipping tooling directories."""
    found: list[Path] = []
    for path in sorted(root.rglob("*.md")):
        parts = path.relative_to(root).parts
        if any(part in SKIPPED_DIRECTORIES for part in parts[:-1]) or not path.is_file():
            continue
        found.append(path)
    return found


def iter_links(file: Path) -> Iterator[Link]:
    """Yield inline links in ``file`` that sit outside fenced blocks and code spans."""
    for number, line in _lines_outside_fences(file):
        stripped = _CODE_SPAN_RE.sub(" ", line)
        for target in _targets_in(stripped):
            yield Link(file=file, line=number, target=target)


def _targets_in(text: str) -> Iterator[str]:
    for match in _LINK_RE.finditer(text):
        angled = match.group("angled")
        target = angled if angled is not None else match.group("bare")
        yield target.strip()
        inner = match.group("text")
        if "](" in inner:
            yield from _targets_in(inner)


def _classify(link: Link, root: Path, report: Report, anchors: dict[Path, frozenset[str]]) -> None:
    lowered = link.target.lower()
    if lowered.startswith(EXTERNAL_PREFIXES):
        report.external += 1
        return
    where = Finding(link.file.relative_to(root).as_posix(), link.line, link.target)
    path_part, _, fragment = link.target.partition("#")
    if _EMAIL_RE.match(path_part):
        report.email.append(where)
        return
    decoded = unquote(path_part)
    if decoded:
        report.relative += 1
    if fragment:
        report.fragments += 1
    target = _resolve(link.file, root, decoded)
    if target is None or not target.exists():
        report.missing.append(where)
        return
    if fragment and target.suffix.lower() in MARKDOWN_SUFFIXES and target.is_file():
        if target not in anchors:
            anchors[target] = frozenset(anchor.lower() for anchor in _anchors_in(target))
        if unquote(fragment).lower() not in anchors[target]:
            report.unresolved.append(where)


def _resolve(file: Path, root: Path, decoded: str) -> Path | None:
    """The on-disk path a link target names; an empty target is the file itself."""
    if not decoded:
        return file
    current = root if decoded.startswith("/") else file.parent
    for part in PurePosixPath(decoded.lstrip("/")).parts:
        if part == "..":
            current = current.parent
        elif part != ".":
            current = current / part
    # Anything that climbs above the checkout is not served by a repository browser.
    return current if current.is_relative_to(root) else None


def _anchors_in(file: Path) -> Iterable[str]:
    """Heading slugs (GitHub style, de-duplicated) and explicit HTML anchors."""
    anchors: list[str] = []
    occurrences: dict[str, int] = {}
    for _, line in _lines_outside_fences(file):
        heading = _HEADING_RE.match(line)
        if heading is not None:
            anchors.append(_unique_slug(slugify(heading.group("text") or ""), occurrences))
        anchors.extend(_ANCHOR_NAME_RE.findall(line))
        anchors.extend(_ANCHOR_ID_RE.findall(line))
    return anchors


def _unique_slug(slug: str, occurrences: dict[str, int]) -> str:
    original = slug
    while slug in occurrences:
        occurrences[original] += 1
        slug = f"{original}-{occurrences[original]}"
    occurrences[slug] = 0
    return slug


def slugify(heading: str) -> str:
    """GitHub's heading slug: strip inline markup, unescape, lowercase, keep word chars."""
    text = _IMAGE_MARKUP_RE.sub("", heading)
    text = _LINK_MARKUP_RE.sub(r"\1", text)
    text = _REFERENCE_MARKUP_RE.sub(r"\1", text)
    text = text.replace("`", "")
    text = _STAR_EMPHASIS_RE.sub(r"\2", text)
    text = _UNDERSCORE_EMPHASIS_RE.sub(r"\2", text)
    text = html.unescape(text).lower()
    text = _SLUG_DROP_RE.sub("", text)
    return text.replace(" ", "-")


def _lines_outside_fences(file: Path) -> Iterator[tuple[int, str]]:
    """Yield ``(line number, line)`` for every line not inside a fenced code block."""
    fence_char = ""
    fence_length = 0
    text = file.read_text(encoding="utf-8", errors="replace")
    for number, line in enumerate(text.split("\n"), start=1):
        if fence_char:
            closing = line.strip()
            if closing and set(closing) == {fence_char} and len(closing) >= fence_length:
                fence_char = ""
            continue
        opened = _FENCE_OPEN_RE.match(line)
        if opened is not None:
            fence_char = opened.group(1)[0]
            fence_length = len(opened.group(1))
            continue
        yield number, line


if __name__ == "__main__":
    raise SystemExit(main())
