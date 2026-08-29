from __future__ import annotations

import ctypes
from pathlib import Path
from typing import BinaryIO

from .errors import AbiError, OutputError, PrimitiveError, ResourceError

BLOOM_PRIMITIVE_ABI_VERSION = 0x00010000
BLOOM_PRIMITIVE_WORKSPACE_ABI_VERSION = 0x00010000
_WORKSPACE_OK = 0
_WORKSPACE_INVALID_ARGUMENT = 1
_WORKSPACE_UNSUPPORTED_SHAPE = 3
_WORKSPACE_INSUFFICIENT = 4
_WORKSPACE_MISALIGNED = 5
_WRITE = ctypes.CFUNCTYPE(
    ctypes.c_int32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t
)


class NativeWorkspacePrimitive:
    """Loader for the opt-in frozen workspace execution family."""

    def __init__(self, artifact: Path, binding) -> None:
        if binding.family != "workspace":
            raise AbiError(f"unsupported execution family: {binding.family}")
        if binding.version != BLOOM_PRIMITIVE_WORKSPACE_ABI_VERSION:
            raise AbiError(
                f"required workspace ABI 0x{binding.version:08x} is not supported "
                f"(runtime workspace ABI 0x{BLOOM_PRIMITIVE_WORKSPACE_ABI_VERSION:08x})"
            )
        try:
            self._library = ctypes.CDLL(str(artifact))
            version = getattr(self._library, "bloom_primitive_workspace_abi_version")
            query = getattr(self._library, binding.query)
            run = getattr(self._library, binding.run)
        except (OSError, AttributeError) as error:
            raise AbiError(f"cannot load workspace primitive ABI: {error}") from error
        version.argtypes = []
        version.restype = ctypes.c_uint32
        query.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
                          ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
        query.restype = ctypes.c_int32
        query_type = _WRITE
        run.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
                        ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
                        query_type, ctypes.c_void_p]
        run.restype = ctypes.c_int32
        if version() != binding.version:
            raise AbiError(
                f"primitive reports workspace ABI 0x{version():08x}, "
                f"manifest requires 0x{binding.version:08x}"
            )
        self._query = query
        self._run = run

    def execute(self, data: bytes, output: BinaryIO, max_workspace_bytes: int) -> None:
        input_storage = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
        required = ctypes.c_size_t(0)
        alignment = ctypes.c_size_t(0)
        query_result = self._query(input_storage, len(data), ctypes.byref(required), ctypes.byref(alignment))
        if query_result != _WORKSPACE_OK:
            raise PrimitiveError(f"workspace query failed with status {query_result}")
        if required.value < 0 or alignment.value < 8 or alignment.value & (alignment.value - 1):
            raise ResourceError("workspace query returned invalid size or alignment")
        if required.value > max_workspace_bytes:
            raise ResourceError(
                f"workspace requirement {required.value} exceeds limit {max_workspace_bytes}"
            )
        if required.value == 0:
            backing = None
            workspace = None
        else:
            try:
                backing = ctypes.create_string_buffer(required.value + alignment.value - 1)
            except (MemoryError, OSError) as error:
                raise ResourceError(f"cannot allocate workspace: {error}") from error
            address = ctypes.addressof(backing)
            aligned = (address + alignment.value - 1) & ~(alignment.value - 1)
            workspace = ctypes.cast(aligned, ctypes.POINTER(ctypes.c_uint8))
        output_error: BaseException | None = None

        def write(_context: int, pointer: ctypes.POINTER(ctypes.c_uint8), size: int) -> int:
            nonlocal output_error
            try:
                chunk = ctypes.string_at(pointer, size) if size else b""
                written = output.write(chunk)
                if written is not None and written != size:
                    raise OSError(f"short output write: {written} of {size} bytes")
                return 0
            except BaseException as error:
                output_error = error
                return -1

        callback = _WRITE(write)
        result = self._run(input_storage, len(data), workspace, required.value, callback, None)
        if output_error is not None:
            raise OutputError(f"cannot write primitive output: {output_error}") from output_error
        if result != _WORKSPACE_OK:
            raise PrimitiveError(f"workspace primitive execution failed with status {result}")


class NativePrimitive:
    """Loader for the two-symbol Bloom primitive ABI v1."""

    def __init__(self, artifact: Path, required_abi: int):
        if required_abi != BLOOM_PRIMITIVE_ABI_VERSION:
            raise AbiError(
                f"required primitive ABI 0x{required_abi:08x} is not supported "
                f"(runtime base 0x{BLOOM_PRIMITIVE_ABI_VERSION:08x})"
            )
        try:
            self._library = ctypes.CDLL(str(artifact))
            version = self._library.bloom_primitive_abi_version
            run = self._library.bloom_primitive_run_vbuf
        except (OSError, AttributeError) as error:
            raise AbiError(f"cannot load primitive ABI: {error}") from error
        version.argtypes = []
        version.restype = ctypes.c_uint32
        run.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t, _WRITE, ctypes.c_void_p]
        run.restype = ctypes.c_int32
        actual = version()
        if actual != required_abi:
            raise AbiError(
                f"primitive reports ABI 0x{actual:08x}, manifest requires 0x{required_abi:08x}"
            )
        self._run = run

    def execute(self, data: bytes, output: BinaryIO) -> None:
        output_error: BaseException | None = None

        def write(_context: int, pointer: ctypes.POINTER(ctypes.c_uint8), size: int) -> int:
            nonlocal output_error
            try:
                chunk = ctypes.string_at(pointer, size) if size else b""
                written = output.write(chunk)
                if written is not None and written != size:
                    raise OSError(f"short output write: {written} of {size} bytes")
                return 0
            except BaseException as error:  # ctypes callbacks cannot propagate exceptions.
                output_error = error
                return -1

        callback = _WRITE(write)
        storage = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
        result = self._run(storage, len(data), callback, None)
        if output_error is not None:
            raise OutputError(f"cannot write primitive output: {output_error}") from output_error
        if result != 0:
            raise PrimitiveError(f"primitive execution failed with status {result}")
