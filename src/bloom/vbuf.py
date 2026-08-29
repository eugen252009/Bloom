from __future__ import annotations

import ctypes
import os
import tempfile
from pathlib import Path

from .errors import VBufError


class VBufValidator:
    """Integration seam to the authoritative vBuf Core v0.6 C API."""

    def __init__(self, library_path: Path):
        self.library_path = library_path.resolve()
        try:
            self._library = ctypes.CDLL(str(self.library_path))
            self._open = self._library.vbuf_v06_open
            self._close = self._library.vbuf_v06_close
        except (OSError, AttributeError) as error:
            raise VBufError(f"cannot load vBuf Core {self.library_path}: {error}") from error
        self._open.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32)]
        self._open.restype = ctypes.c_void_p
        self._close.argtypes = [ctypes.c_void_p]
        self._close.restype = None

    def validate(self, data: bytes) -> None:
        # vBuf Core's current validated C entry point opens a path. Spooling is
        # isolated here so a future bounded-memory API can replace it cleanly.
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix="bloom-vbuf-", suffix=".vbuf", delete=False) as stream:
                temporary_name = stream.name
                stream.write(data)
                stream.flush()
            error = ctypes.c_uint32(0)
            handle = self._open(os.fsencode(temporary_name), ctypes.byref(error))
            if not handle:
                raise VBufError(f"vBuf Core rejected input (error {error.value})")
            self._close(handle)
        except OSError as exception:
            raise VBufError(f"cannot validate vBuf input: {exception}") from exception
        finally:
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass
