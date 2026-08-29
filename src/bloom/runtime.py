from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from .abi import NativePrimitive, NativeWorkspacePrimitive
from .artifact import validate_artifact
from .errors import ResourceError
from .model import Capability
from .vbuf import VBufValidator


class Runtime:
    """Execution boundary independent of CLI and catalog implementations."""

    def __init__(self, vbuf_core_library: Path, max_workspace_bytes: int | None = None):
        self._vbuf = VBufValidator(vbuf_core_library)
        if max_workspace_bytes is not None and max_workspace_bytes < 0:
            raise ValueError("max_workspace_bytes must not be negative")
        self._max_workspace_bytes = max_workspace_bytes

    def run(self, capability: Capability, stdin: BinaryIO, stdout: BinaryIO) -> None:
        with validate_artifact(capability) as artifact:
            if capability.execution is None:
                primitive = NativePrimitive(artifact.load_path, capability.artifact.abi_base)
            else:
                primitive = NativeWorkspacePrimitive(artifact.load_path, capability.execution)
        data = stdin.read()
        if not isinstance(data, bytes):
            raise TypeError("runtime input stream must be binary")
        self._vbuf.validate(data)
        if capability.execution is None:
            primitive.execute(data, stdout)
        else:
            if self._max_workspace_bytes is None:
                raise ResourceError("workspace execution requires max_workspace_bytes")
            primitive.execute(data, stdout, self._max_workspace_bytes)
        stdout.flush()
