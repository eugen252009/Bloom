from __future__ import annotations

import hashlib
import os
import platform
import shutil
import stat
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import ArtifactValidationError
from .model import Capability

_BASE_SYMBOLS = {
    "bloom_primitive_abi_version",
    "bloom_primitive_run_vbuf",
}
_MACHINE = {"x86_64": 62, "aarch64": 183, "riscv64": 243}
_TARGET_ARCH = {"amd64": "x86_64", "x86_64": "x86_64", "aarch64": "aarch64", "riscv64": "riscv64"}


def current_target() -> str:
    machine = _TARGET_ARCH.get(platform.machine().lower())
    if machine is None or platform.system() != "Linux":
        raise ArtifactValidationError(
            f"native artifacts are not implemented for {platform.system()}/{platform.machine()}"
        )
    libc_name, _ = platform.libc_ver()
    suffix = "gnu" if libc_name in ("", "glibc") else libc_name
    return f"{machine}-linux-{suffix}"


@dataclass
class ValidatedArtifact:
    source_path: Path
    _fd: int

    @property
    def load_path(self) -> Path:
        # Keep dlopen bound to the inode that was hashed and inspected.
        return Path(f"/proc/{os.getpid()}/fd/{self._fd}")

    def close(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> "ValidatedArtifact":
        return self

    def __exit__(self, *_error: object) -> None:
        self.close()


def _readelf(path: Path, *arguments: str) -> str:
    executable = shutil.which("readelf")
    if executable is None:
        raise ArtifactValidationError("native artifact validation requires readelf")
    result = subprocess.run(
        [executable, *arguments, str(path)], capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "readelf rejected the artifact"
        raise ArtifactValidationError(f"invalid native artifact: {detail}")
    return result.stdout


def _validate_elf(path: Path, target: str, required_symbols: set[str] | None = None) -> None:
    try:
        with path.open("rb") as artifact:
            header = artifact.read(20)
    except OSError as error:
        raise ArtifactValidationError(f"cannot read artifact {path}: {error}") from error
    if len(header) < 20 or header[:4] != b"\x7fELF":
        raise ArtifactValidationError("artifact is not an ELF binary")
    if header[4] != 2 or header[5] != 1:
        raise ArtifactValidationError("only little-endian ELF64 artifacts are implemented")
    elf_type, machine = struct.unpack_from("<HH", header, 16)
    if elf_type != 3:
        raise ArtifactValidationError("native artifact is not an ELF shared object")
    architecture = target.split("-", 1)[0]
    expected_machine = _MACHINE.get(architecture)
    if expected_machine is None or machine != expected_machine:
        raise ArtifactValidationError("artifact ELF machine does not match its target")

    dynamic = _readelf(path, "--dynamic", "--wide")
    forbidden_tags = ("(NEEDED)", "(INIT)", "(INIT_ARRAY)")
    present = [tag for tag in forbidden_tags if tag in dynamic]
    if present:
        raise ArtifactValidationError(
            "pure native artifact has forbidden dynamic entries: " + ", ".join(present)
        )

    symbols = _readelf(path, "--dyn-syms", "--wide")
    defined: set[str] = set()
    unresolved: set[str] = set()
    for line in symbols.splitlines():
        fields = line.split()
        if len(fields) < 8 or not fields[0].rstrip(":").isdigit():
            continue
        symbol_type, binding, index, name = fields[3], fields[4], fields[6], fields[7]
        name = name.split("@", 1)[0]
        if index == "UND" and binding != "LOCAL" and name:
            unresolved.add(name)
        elif index != "UND" and binding == "GLOBAL" and symbol_type == "FUNC":
            defined.add(name)
    missing = (required_symbols or _BASE_SYMBOLS) - defined
    if missing:
        raise ArtifactValidationError(
            "artifact is missing required exports: " + ", ".join(sorted(missing))
        )
    if unresolved:
        raise ArtifactValidationError(
            "pure native artifact has unresolved imports: " + ", ".join(sorted(unresolved))
        )


def validate_artifact(capability: Capability) -> ValidatedArtifact:
    artifact = capability.artifact
    if artifact.format != "native-so":
        raise ArtifactValidationError(f"unsupported artifact format: {artifact.format}")
    if capability.effects:
        raise ArtifactValidationError("this runtime slice admits only effect-free primitives")
    host_target = current_target()
    if artifact.target != host_target:
        raise ArtifactValidationError(
            f"artifact target {artifact.target!r} is incompatible with host {host_target!r}"
        )
    if not artifact.identity.startswith("sha256:"):
        raise ArtifactValidationError("only sha256 artifact identities are implemented")
    try:
        fd = os.open(artifact.path, os.O_RDONLY | os.O_CLOEXEC)
    except OSError as error:
        raise ArtifactValidationError(f"cannot open artifact {artifact.path}: {error}") from error
    validated = ValidatedArtifact(artifact.path, fd)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ArtifactValidationError(f"artifact is not a regular file: {artifact.path}")
        digest = hashlib.sha256()
        os.lseek(fd, 0, os.SEEK_SET)
        while chunk := os.read(fd, 1024 * 1024):
            digest.update(chunk)
        actual = "sha256:" + digest.hexdigest()
        if actual != artifact.identity:
            raise ArtifactValidationError(
                f"artifact identity mismatch: expected {artifact.identity}, got {actual}"
            )
        if capability.execution is None:
            required_symbols = _BASE_SYMBOLS
        else:
            # The fixed family-version export plus the capability binding's
            # paired query/run symbols must exist in this exact artifact.
            required_symbols = {
                "bloom_primitive_workspace_abi_version",
                capability.execution.query,
                capability.execution.run,
            }
        _validate_elf(validated.load_path, artifact.target, required_symbols)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise ArtifactValidationError("artifact changed during validation")
        return validated
    except (OSError, ArtifactValidationError) as error:
        validated.close()
        if isinstance(error, ArtifactValidationError):
            raise
        raise ArtifactValidationError(f"cannot validate artifact: {error}") from error
