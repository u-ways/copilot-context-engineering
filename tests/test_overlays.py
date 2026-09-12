"""Packaged overlays are dotless, git-tracked, deduplicated and licence-clean (ADR-0005)."""

import hashlib
import subprocess
from pathlib import Path

from cce.manifest import load, split_front_matter
from cce.render import OVERLAYS_ROOT, load_procedures

REPO_ROOT = Path(__file__).resolve().parent.parent


def overlay_files() -> list[Path]:
    return sorted(path for path in OVERLAYS_ROOT.rglob("*") if path.is_file())


class TestPackageData:
    def test_no_path_segment_starts_with_a_dot(self) -> None:
        offenders = [
            path.relative_to(OVERLAYS_ROOT).as_posix()
            for path in overlay_files()
            if any(part.startswith(".") for part in path.relative_to(OVERLAYS_ROOT).parts)
        ]

        assert offenders == []

    def test_every_overlay_file_is_visible_to_git(self) -> None:
        listing = subprocess.run(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                "src/cce/overlays",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split("\n")
        visible = {REPO_ROOT / line for line in listing if line}

        assert set(overlay_files()) <= visible

    def test_no_hand_written_skill_files(self) -> None:
        assert [path for path in overlay_files() if path.name == "SKILL.md"] == []


class TestProcedures:
    def test_bodies_are_distinct(self) -> None:
        hashes = [hashlib.sha256(p.source.encode()).hexdigest() for p in load_procedures(load())]

        assert len(set(hashes)) == len(hashes)

    def test_every_procedure_ends_with_its_tracer_line(self) -> None:
        for procedure in load_procedures(load()):
            assert procedure.source.rstrip().endswith(f"`procedure: {procedure.name}`.")

    def test_descriptions_match_the_documented_routing_text(self) -> None:
        descriptions = {p.name: p.description for p in load_procedures(load())}

        assert descriptions["convert-page-to-framework-conventions"].startswith("Rewrite a legacy")
        assert descriptions["publish-and-open-source-a-repository"].startswith("Publish code")
        for name in ("engineering-maturity-review", "observability-and-reliability"):
            lowered = descriptions[name].lower()
            assert "metric" not in lowered and "dashboard" not in lowered, name


class TestAgents:
    def test_agent_front_matter_declares_the_documented_tools(self) -> None:
        agents = OVERLAYS_ROOT / "_shared" / "agents"
        expected = {
            "researcher": ["read", "search", "web"],
            "author": ["read", "search", "edit"],
            "validator": ["read", "search", "execute"],
            "auditor": ["read", "search", "execute"],
        }

        for name, tools in expected.items():
            fields, _ = split_front_matter((agents / f"{name}.agent.md").read_text())
            assert fields["name"] == name
            assert fields["tools"] == tools, name
