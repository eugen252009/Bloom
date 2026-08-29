#!/usr/bin/env python3
"""Create a checked local catalog from capability templates and built artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def render(template: Path, artifact: Path, output: Path, target: str) -> list[dict[str, Any]]:
    artifact = artifact.resolve(strict=True)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    artifact_path = os.path.relpath(artifact, output.parent)
    text = template.read_text(encoding="utf-8")
    text = text.replace("@ARTIFACT_IDENTITY@", f"sha256:{digest}")
    text = text.replace("@ARTIFACT_PATH@", Path(artifact_path).as_posix())
    text = text.replace("@TARGET@", target)
    parsed = json.loads(text)
    if set(parsed) != {"schema_version", "capabilities"} or parsed["schema_version"] != 1:
        raise ValueError(f"unsupported capability template schema: {template}")
    if not isinstance(parsed["capabilities"], list):
        raise ValueError(f"template capabilities must be an array: {template}")
    return parsed["capabilities"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--capability", action="append", nargs=2, required=True,
        metavar=("TEMPLATE", "ARTIFACT"),
        help="capability manifest template and its built artifact; repeatable",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target", required=True)
    options = parser.parse_args()

    output = options.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    capabilities: list[dict[str, Any]] = []
    for template, artifact in options.capability:
        capabilities.extend(render(Path(template), Path(artifact), output, options.target))
    names = [entry.get("name") for entry in capabilities]
    if len(names) != len(set(names)):
        raise ValueError("duplicate capability names in generated catalog")

    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps({"schema_version": 1, "capabilities": capabilities}, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
