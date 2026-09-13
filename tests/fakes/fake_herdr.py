"""A fake ``herdr`` that records argv and answers with canned JSON.

Environment: ``FAKE_HERDR_LOG`` (append one JSON line per call), ``FAKE_HERDR_LABELS``
(comma-separated labels ``workspace list`` reports), ``FAKE_HERDR_FAIL_ON``
(a ``group verb`` prefix that exits 1), ``FAKE_HERDR_COUNTER`` (file holding a
counter so ids are unique across calls).
"""

import json
import os
import sys
from pathlib import Path


def next_id(prefix: str) -> str:
    base = os.environ.get("FAKE_HERDR_COUNTER")
    if not base:
        return f"{prefix}1"
    counter = Path(f"{base}.{prefix}")
    value = int(counter.read_text() or "0") + 1 if counter.is_file() else 1
    counter.write_text(str(value))
    return f"{prefix}{value}"


def main() -> int:
    args = sys.argv[1:]
    log = os.environ.get("FAKE_HERDR_LOG")
    if log:
        with Path(log).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(args) + "\n")
    head = " ".join(args[:2])
    if os.environ.get("FAKE_HERDR_FAIL_ON") and head.startswith(os.environ["FAKE_HERDR_FAIL_ON"]):
        print("simulated failure", file=sys.stderr)
        return 1
    result: dict[str, object]
    if head == "workspace list":
        labels = [label for label in os.environ.get("FAKE_HERDR_LABELS", "").split(",") if label]
        result = {"type": "workspace_list", "workspaces": [{"label": label} for label in labels]}
    elif head == "workspace create":
        wid = next_id("w")
        result = {
            "workspace": {"workspace_id": wid},
            "tab": {"tab_id": f"{wid}:t1"},
            "root_pane": {"pane_id": f"{wid}:p1"},
        }
    elif head == "tab create":
        tid = next_id("t")
        result = {"tab": {"tab_id": tid}, "root_pane": {"pane_id": f"{tid}:p1"}}
    else:
        result = {"ok": True}
    print(json.dumps({"id": "cli:" + head.replace(" ", ":"), "result": result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
