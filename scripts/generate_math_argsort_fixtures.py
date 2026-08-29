#!/usr/bin/env python3
"""Generate authoritative vBuf fixtures for math.argsort.u32."""
from __future__ import annotations

import argparse
import ctypes
from pathlib import Path

U16, U32, U64 = 1, 2, 3
ARRAY, SCALAR = 1, 0

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

    def one_block(self, path: Path, values: list[int], value_type: int = U32,
                  physical: int = ARRAY) -> None:
        c_type = {U16: ctypes.c_uint16, U32: ctypes.c_uint32, U64: ctypes.c_uint64}[value_type]
        data = (c_type * len(values))(*values)
        error = ctypes.c_uint32()
        handle = self.create(str(path).encode(), 3, False, ctypes.byref(error))
        if not handle:
            raise RuntimeError(f"writer create failed ({error.value})")
        if self.write(handle, 0, physical, False, 0, value_type,
                      ctypes.cast(data, ctypes.c_void_p), len(values)) != 0:
            raise RuntimeError(f"writer write failed: {path}")
        if self.finish(handle) != 0:
            raise RuntimeError(f"writer finish failed: {path}")


def add_case(writer: Writer, output: Path, name: str, values: list[int]) -> None:
    writer.one_block(output / f"{name}-input.vbuf", values)
    expected = sorted(range(len(values)), key=lambda index: (values[index], index))
    writer.one_block(output / f"{name}-expected.vbuf", expected, value_type=U64)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vbuf-library", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    options.output.mkdir(parents=True, exist_ok=True)
    writer = Writer(options.vbuf_library)
    cases = {
        "normal": [24, 7, 42, 7],
        "sorted": [1, 2, 3, 4],
        "reverse": [4, 3, 2, 1],
        "duplicates": [5, 1, 5, 1, 5],
        "equal": [7, 7, 7, 7],
        "single": [123],
        "boundary": [0xFFFFFFFF, 0, 0x80000000, 1],
        "empty": [],
    }
    for name, values in cases.items():
        add_case(writer, options.output, name, values)
    writer.one_block(options.output / "wrong-u16-input.vbuf", [1, 2], value_type=U16)
    writer.one_block(options.output / "wrong-u64-input.vbuf", [1, 2], value_type=U64)
    writer.one_block(options.output / "wrong-scalar-input.vbuf", [1], physical=SCALAR)
    writer.one_block(options.output / "large-100k-input.vbuf", list(range(100_000, 0, -1)))
    writer.one_block(options.output / "large-100k-expected.vbuf",
                     list(range(99_999, -1, -1)), value_type=U64)
    (options.output / ".stamp").write_text("authoritative vBuf Core v0.6 fixtures\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
