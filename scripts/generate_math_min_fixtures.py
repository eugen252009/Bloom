#!/usr/bin/env python3
"""Generate math.min.u32 fixtures through authoritative vBuf Core v0.6."""
from __future__ import annotations

import argparse
import ctypes
from pathlib import Path

U16 = 1
U32 = 2
U64 = 3
ARRAY = 1
SCALAR = 0
KEY_ID = 1


class Writer:
    def __init__(self, library: Path):
        self.library = ctypes.CDLL(str(library.resolve(strict=True)))
        self.create = self.library.vbuf_v06_writer_create
        self.create.argtypes = [ctypes.c_char_p, ctypes.c_uint8, ctypes.c_bool,
                                ctypes.POINTER(ctypes.c_uint32)]
        self.create.restype = ctypes.c_void_p
        self.write = self.library.vbuf_v06_writer_write
        self.write.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint8,
                               ctypes.c_bool, ctypes.c_uint8, ctypes.c_uint8,
                               ctypes.c_void_p, ctypes.c_size_t]
        self.write.restype = ctypes.c_uint32
        self.finish = self.library.vbuf_v06_writer_finish
        self.finish.argtypes = [ctypes.c_void_p]
        self.finish.restype = ctypes.c_uint32

    def one_block(self, path: Path, values: list[int], *, value_type: int = U32,
                  physical: int = ARRAY, key_id: int = KEY_ID) -> None:
        c_types = {U16: ctypes.c_uint16, U32: ctypes.c_uint32, U64: ctypes.c_uint64}
        try:
            c_type = c_types[value_type]
        except KeyError as error:
            raise ValueError(f"unsupported fixture value type: {value_type}") from error
        data = (c_type * len(values))(*values)
        error = ctypes.c_uint32()
        handle = self.create(str(path).encode(), 3, False, ctypes.byref(error))
        if not handle:
            raise RuntimeError(f"vBuf writer create failed ({error.value}): {path}")
        if self.write(handle, key_id, physical, False, 0, value_type,
                      ctypes.cast(data, ctypes.c_void_p), len(values)) != 0:
            raise RuntimeError(f"vBuf writer write failed: {path}")
        if self.finish(handle) != 0:
            raise RuntimeError(f"vBuf writer finish failed: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vbuf-library", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    options.output.mkdir(parents=True, exist_ok=True)
    writer = Writer(options.vbuf_library)

    cases = {
        "normal": ([42, 7, 900, 23, 11], 7),
        "boundary": ([0xFFFFFFFF, 0], 0),
        "single": ([123456789], 123456789),
    }
    for name, (values, expected) in cases.items():
        writer.one_block(options.output / f"{name}-input.vbuf", values)
        writer.one_block(options.output / f"{name}-expected.vbuf", [expected], physical=SCALAR)
    writer.one_block(options.output / "empty-input.vbuf", [])
    writer.one_block(options.output / "wrong-u16-input.vbuf", [7, 3, 9], value_type=U16)
    writer.one_block(options.output / "wrong-scalar-input.vbuf", [7], physical=SCALAR)

    # Developer-only bulk sanity input; no timing threshold is attached.
    large = list(range(100_000, 0, -1))
    large.append(0)
    writer.one_block(options.output / "large-100k-input.vbuf", large)
    writer.one_block(options.output / "large-100k-expected.vbuf", [0], physical=SCALAR)
    (options.output / ".stamp").write_text("authoritative vBuf Core v0.6 fixtures\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
