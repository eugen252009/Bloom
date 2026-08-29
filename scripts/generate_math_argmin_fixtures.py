#!/usr/bin/env python3
"""Generate math.argmin.u32 fixtures through authoritative vBuf Core v0.6."""
from __future__ import annotations

import argparse
from pathlib import Path

from generate_math_min_fixtures import ARRAY, SCALAR, U16, U32, U64, Writer

INPUT_KEY_ID = 37
RESULT_KEY_ID = 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vbuf-library", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    options.output.mkdir(parents=True, exist_ok=True)
    writer = Writer(options.vbuf_library)

    cases = {
        "normal": ([42, 7, 900, 23, 11], 1),
        "beginning": ([1, 5, 10], 0),
        "end": ([10, 5, 1], 2),
        "duplicate": ([10, 4, 8, 4, 9], 1),
        "single": ([123], 0),
        "boundary": ([0xFFFFFFFF, 0, 0xFFFFFFFF, 0], 1),
    }
    for name, (values, expected) in cases.items():
        writer.one_block(
            options.output / f"{name}-input.vbuf", values, key_id=INPUT_KEY_ID
        )
        writer.one_block(
            options.output / f"{name}-expected.vbuf", [expected],
            value_type=U64, physical=SCALAR, key_id=RESULT_KEY_ID,
        )

    writer.one_block(options.output / "empty-input.vbuf", [], key_id=INPUT_KEY_ID)
    writer.one_block(
        options.output / "wrong-u16-input.vbuf", [7, 3, 9],
        value_type=U16, key_id=INPUT_KEY_ID,
    )
    writer.one_block(
        options.output / "wrong-u64-input.vbuf", [7, 3, 9],
        value_type=U64, key_id=INPUT_KEY_ID,
    )
    writer.one_block(
        options.output / "wrong-scalar-input.vbuf", [7],
        physical=SCALAR, key_id=INPUT_KEY_ID,
    )

    # Developer-only bulk sanity input; no timing threshold is attached.
    large = list(range(100_000, 0, -1))
    large.append(0)
    writer.one_block(options.output / "large-100k-input.vbuf", large, key_id=INPUT_KEY_ID)
    writer.one_block(
        options.output / "large-100k-expected.vbuf", [100_000],
        value_type=U64, physical=SCALAR, key_id=RESULT_KEY_ID,
    )
    (options.output / ".stamp").write_text("authoritative vBuf Core v0.6 fixtures\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
