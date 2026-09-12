"""Diagnostics go to the configured stream as console or JSON lines (ADR-0006)."""

import io
import json

from cce.log import LogFormat, configure, get_logger


class TestJsonFormat:
    def test_writes_one_json_object_per_record(self) -> None:
        stream = io.StringIO()
        configure(verbosity=0, fmt=LogFormat.JSON, stream=stream)

        get_logger("test").info("hello", answer=42)

        record = json.loads(stream.getvalue())
        assert record["event"] == "hello"
        assert record["level"] == "info"
        assert record["answer"] == 42
        assert "timestamp" in record


class TestConsoleFormat:
    def test_renders_the_event_and_context_as_text(self) -> None:
        stream = io.StringIO()
        configure(verbosity=0, fmt=LogFormat.CONSOLE, stream=stream)

        get_logger("test").info("hello", answer=42)

        assert "hello" in stream.getvalue()
        assert "answer=42" in stream.getvalue()


class TestVerbosity:
    def test_quiet_hides_info_but_keeps_warnings(self) -> None:
        stream = io.StringIO()
        configure(verbosity=-1, fmt=LogFormat.JSON, stream=stream)

        logger = get_logger("test")
        logger.info("hidden")
        logger.warning("shown")

        assert "hidden" not in stream.getvalue()
        assert "shown" in stream.getvalue()

    def test_default_hides_debug(self) -> None:
        stream = io.StringIO()
        configure(verbosity=0, fmt=LogFormat.JSON, stream=stream)

        get_logger("test").debug("hidden")

        assert stream.getvalue() == ""

    def test_verbose_shows_debug_and_clamps_higher_values(self) -> None:
        stream = io.StringIO()
        configure(verbosity=5, fmt=LogFormat.JSON, stream=stream)

        get_logger("test").debug("shown")

        assert json.loads(stream.getvalue())["level"] == "debug"
