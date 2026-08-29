from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from .errors import BloomError
from .registry import LocalCatalog
from .runtime import Runtime


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bloom")
    parser.add_argument(
        "--catalog", type=Path,
        default=Path(os.environ.get("BLOOM_CATALOG", "build/catalog.json")),
        help="local catalog path (default: BLOOM_CATALOG or build/catalog.json)",
    )
    parser.add_argument(
        "--vbuf-library", type=Path,
        default=Path(os.environ.get("BLOOM_VBUF_LIBRARY", "libvbuf_core.so")),
        help="authoritative vBuf Core shared library",
    )
    parser.add_argument(
        "--max-workspace-bytes", type=int,
        default=(int(os.environ["BLOOM_MAX_WORKSPACE_BYTES"])
                 if "BLOOM_MAX_WORKSPACE_BYTES" in os.environ else None),
        help="maximum workspace for workspace capabilities (disabled by default)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities", help="list locally known capabilities")
    describe = commands.add_parser("describe", help="describe one capability")
    describe.add_argument("capability")
    run = commands.add_parser("run", help="execute one capability over binary stdin/stdout")
    run.add_argument("capability")
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    parser = _parser()
    options = parser.parse_args(arguments)
    try:
        catalog = LocalCatalog(options.catalog)
        if options.command == "capabilities":
            for capability in catalog.list():
                print(capability.name)
            return 0
        if options.command == "describe":
            print(json.dumps(catalog.describe(options.capability).describe(), indent=2, sort_keys=True))
            return 0
        if options.command == "run":
            capability = catalog.resolve(options.capability)
            Runtime(options.vbuf_library, options.max_workspace_bytes).run(
                capability, sys.stdin.buffer, sys.stdout.buffer
            )
            return 0
        parser.error("missing command")
    except BloomError as error:
        print(f"bloom: {error}", file=sys.stderr)
        return error.exit_code
    except BrokenPipeError:
        return 8
    except Exception as error:
        print(f"bloom: internal error: {error}", file=sys.stderr)
        return 1
    return 1
