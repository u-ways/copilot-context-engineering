"""The manifest declares every scenario; ids and front matter parse strictly (ADR-0005)."""

import pytest

from cce import CceError
from cce.manifest import (
    FrontMatterValue,
    ManifestError,
    as_list,
    load,
    parse,
    render_front_matter,
    resolve_ids,
    split_front_matter,
)

VALID = """
[source]
url = "file:///tmp/upstream"
ref = "0123456789abcdef0123456789abcdef01234567"

[[scenario]]
id = "01"
slug = "01-first-lesson"
title = "First"

[[scenario]]
id = "02"
slug = "02-second-lesson"
title = "Second"
"""


class TestPackagedManifest:
    def test_declares_six_scenarios_in_order(self) -> None:
        manifest = load()

        assert [scenario.id for scenario in manifest.scenarios] == [
            "01",
            "02",
            "03",
            "04",
            "05",
            "06",
        ]
        assert all(s.slug.startswith(f"{s.id}-") for s in manifest.scenarios)

    def test_pins_a_full_commit_sha(self) -> None:
        manifest = load()

        assert len(manifest.source_ref) == 40
        assert manifest.source_url.startswith("https://github.com/")


class TestScenarioIds:
    def test_accepts_every_documented_id_form(self) -> None:
        manifest = parse(VALID)

        for token in ("2", "02", "02-second-lesson", "second-lesson"):
            assert manifest.find(token) == manifest.scenarios[1], token

    def test_no_tokens_means_every_scenario(self) -> None:
        manifest = parse(VALID)

        assert resolve_ids(manifest, []) == list(manifest.scenarios)

    def test_deduplicates_and_keeps_user_order(self) -> None:
        manifest = parse(VALID)

        assert resolve_ids(manifest, ["2", "1", "02"]) == [
            manifest.scenarios[1],
            manifest.scenarios[0],
        ]

    def test_unknown_id_is_a_usage_error_listing_valid_slugs(self) -> None:
        manifest = parse(VALID)

        with pytest.raises(CceError) as raised:
            resolve_ids(manifest, ["99"])

        assert raised.value.exit_code == 2
        assert "01-first-lesson, 02-second-lesson" in str(raised.value)

    def test_name_strips_the_numeric_prefix(self) -> None:
        assert parse(VALID).scenarios[0].name == "first-lesson"


class TestManifestValidation:
    @pytest.mark.parametrize(
        ("mutation", "message"),
        [
            (
                lambda t: t.replace(
                    'ref = "0123456789abcdef0123456789abcdef01234567"', 'ref = "main"'
                ),
                "40-character",
            ),
            (
                lambda t: t.replace('[source]\nurl = "file:///tmp/upstream"\n', "[source]\n"),
                "source.url",
            ),
            (lambda t: t.split("[[scenario]]")[0], "declares no"),
            (
                lambda t: t.replace('title = "Second"', 'title = "Second"\nextra = 1'),
                "unknown keys",
            ),
            (lambda t: t.replace('id = "02"', 'id = "2"'), "two digits"),
            (
                lambda t: t.replace('slug = "02-second-lesson"', 'slug = "03-second-lesson"'),
                "02-<name>",
            ),
            (
                lambda t: t.replace('id = "02"', 'id = "01"').replace("02-second", "01-second"),
                "twice",
            ),
            (lambda t: t + "\n[[scenario]\n", "not valid TOML"),
        ],
    )
    def test_rejects_malformed_manifests(self, mutation: object, message: str) -> None:
        assert callable(mutation)
        with pytest.raises(ManifestError, match=message):
            parse(mutation(VALID))


class TestFrontMatter:
    def test_parses_plain_quoted_and_list_values(self) -> None:
        text = (
            "---\n"
            "name: plain-name\n"
            'description: "Do this: then that"\n'
            'tools: [read, "search"]\n'
            "---\n"
            "Body line\n"
        )
        fields, body = split_front_matter(text)

        assert fields == {
            "name": "plain-name",
            "description": "Do this: then that",
            "tools": ["read", "search"],
        }
        assert body == "Body line\n"

    def test_as_list_accepts_comma_separated_strings(self) -> None:
        assert as_list("read, search") == ["read", "search"]
        assert as_list(["read"]) == ["read"]

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            ("name: x\n---\n", "must start"),
            ("---\nname: x\n", "not closed"),
            ("---\nno separator here\n---\n", "not 'key: value'"),
            ("---\nname: a\nname: b\n---\n", "repeats"),
            ("---\ntools: [read\n---\n", "unclosed list"),
        ],
    )
    def test_rejects_malformed_blocks(self, text: str, message: str) -> None:
        with pytest.raises(ManifestError, match=message):
            split_front_matter(text)

    def test_render_quotes_strings_and_round_trips(self) -> None:
        fields: dict[str, FrontMatterValue] = {
            "name": "x",
            "description": 'Say "hi": now',
            "tools": ["read", "edit"],
        }

        rendered = render_front_matter(fields)

        assert rendered.splitlines()[2] == 'description: "Say \\"hi\\": now"'
        assert split_front_matter(rendered + "body")[0] == fields
