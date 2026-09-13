"""A fake ``uv`` that records its arguments and exits with ``FAKE_UV_EXIT``."""

import json
import os
import sys
from pathlib import Path


def main() -> int:
    log = os.environ.get("FAKE_UV_LOG")
    if log:
        with Path(log).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(sys.argv[1:]) + "\n")
    return int(os.environ.get("FAKE_UV_EXIT", "0"))


if __name__ == "__main__":
    raise SystemExit(main())
