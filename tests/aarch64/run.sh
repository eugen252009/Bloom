#!/bin/bash
set -euo pipefail

source_root=/work/src
build_root=/work/build
aarch64_build="$build_root/aarch64-abi"
rust_artifact="$build_root/aarch64-rust/aarch64-unknown-linux-gnu/debug/libbloom_test_rust_identity.so"
workspace_rust_artifact="$build_root/aarch64-rust-workspace/aarch64-unknown-linux-gnu/debug/libbloom_test_rust_workspace.so"
fixture=/work/vbuf/tests/fixtures/v06/valid-basic.vbuf
mkdir -p "$aarch64_build"

cc=aarch64-linux-gnu-gcc
pure_flags=(-std=c11 -fPIC -shared -nostdlib -Wl,--no-undefined -I"$source_root/include")
"$cc" "${pure_flags[@]}" -DBLOOM_PRIMITIVE_IMPLEMENTATION=1 \
  "$source_root/tests/fixtures/aarch64_abi_identity.c" \
  -o "$aarch64_build/libtest_c_identity.so"
"$cc" "${pure_flags[@]}" -DBLOOM_PRIMITIVE_IMPLEMENTATION=1 \
  "$source_root/tests/fixtures/missing_symbol.c" \
  -o "$aarch64_build/libtest_missing_symbol.so"
"$cc" "${pure_flags[@]}" -DBLOOM_PRIMITIVE_IMPLEMENTATION=1 \
  "$source_root/tests/fixtures/incompatible_abi.c" \
  -o "$aarch64_build/libtest_incompatible_abi.so"
"$cc" -std=c11 -fPIC -shared -I"$source_root/include" \
  -DBLOOM_PRIMITIVE_IMPLEMENTATION=1 \
  "$source_root/tests/aarch64/dependent_primitive.c" \
  -o "$aarch64_build/libtest_dependent.so"
"$cc" "${pure_flags[@]}" -DBLOOM_PRIMITIVE_IMPLEMENTATION=1 \
  "$source_root/tests/fixtures/workspace_identity.c" \
  -o "$aarch64_build/libtest_workspace_identity.so"
"$cc" -std=c11 -I"$source_root/include" \
  "$source_root/tests/aarch64/abi_runner.c" -ldl \
  -o "$aarch64_build/abi_runner"
"$cc" -std=c11 -I"$source_root/include" \
  "$source_root/tests/aarch64/workspace_runner.c" -ldl \
  -o "$aarch64_build/workspace_runner"

test -f "$rust_artifact"
test -f "$workspace_rust_artifact"
test -f "$fixture"

PYTHONPATH="$source_root/src" python3 - <<'PY'
import hashlib
from pathlib import Path
from unittest.mock import patch
from bloom.artifact import _validate_elf, validate_artifact
from bloom.errors import ArtifactValidationError
from bloom.model import Artifact, Capability

root = Path("/work/build")
aarch = root / "aarch64-abi"
accepted = (
    aarch / "libtest_c_identity.so",
    root / "aarch64-rust/aarch64-unknown-linux-gnu/debug/libbloom_test_rust_identity.so",
)

def capability(path: Path, target: str) -> Capability:
    identity = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return Capability(
        name="bytes.identity", contract_version="1.0.0", available=True,
        artifact=Artifact("native-so", identity, path, target, 0x00010000),
        input={}, output={}, deterministic=True, effects=(), streaming={},
    )

for artifact in accepted:
    _validate_elf(artifact, "aarch64-linux-gnu")
    with patch("bloom.artifact.current_target", return_value="aarch64-linux-gnu"):
        with validate_artifact(capability(artifact, "aarch64-linux-gnu")):
            pass

# Real x86 host target matching rejects AArch64, and simulated AArch64 target
# matching rejects the existing x86 artifact before either can be loaded.
try:
    validate_artifact(capability(accepted[0], "aarch64-linux-gnu"))
except ArtifactValidationError as error:
    assert "incompatible with host" in str(error)
else:
    raise AssertionError("x86 host accepted AArch64 artifact")
with patch("bloom.artifact.current_target", return_value="aarch64-linux-gnu"):
    try:
        validate_artifact(capability(root / "primitives/libbytes_identity.so",
                                     "x86_64-linux-gnu"))
    except ArtifactValidationError as error:
        assert "incompatible with host" in str(error)
    else:
        raise AssertionError("AArch64 target accepted x86 artifact")

negative = (
    (aarch / "libtest_dependent.so", "aarch64-linux-gnu", "forbidden dynamic entries"),
    (aarch / "libtest_c_identity.so", "x86_64-linux-gnu", "machine does not match"),
    (root / "primitives/libbytes_identity.so", "aarch64-linux-gnu", "machine does not match"),
)
for artifact, target, expected in negative:
    try:
        _validate_elf(artifact, target)
    except ArtifactValidationError as error:
        if expected not in str(error):
            raise AssertionError(f"unexpected rejection for {artifact}: {error}") from error
    else:
        raise AssertionError(f"expected rejection for {artifact} as {target}")
PY

qemu=(qemu-aarch64 -L /usr/aarch64-linux-gnu)
"${qemu[@]}" "$aarch64_build/abi_runner" \
  "$aarch64_build/libtest_c_identity.so" "$fixture" "$aarch64_build/c-output.vbuf"
"${qemu[@]}" "$aarch64_build/abi_runner" \
  "$rust_artifact" "$fixture" "$aarch64_build/rust-output.vbuf"
"${qemu[@]}" "$aarch64_build/workspace_runner" \
  "$aarch64_build/libtest_workspace_identity.so" "$fixture"
"${qemu[@]}" "$aarch64_build/workspace_runner" \
  "$workspace_rust_artifact" "$fixture"
cmp "$fixture" "$aarch64_build/c-output.vbuf"
cmp "$fixture" "$aarch64_build/rust-output.vbuf"
cmp "$aarch64_build/c-output.vbuf" "$aarch64_build/rust-output.vbuf"

set +e
"${qemu[@]}" "$aarch64_build/abi_runner" \
  "$aarch64_build/libtest_missing_symbol.so" "$fixture" "$aarch64_build/missing.vbuf"
missing_status=$?
"${qemu[@]}" "$aarch64_build/abi_runner" \
  "$aarch64_build/libtest_incompatible_abi.so" "$fixture" "$aarch64_build/incompatible.vbuf"
abi_status=$?
set -e
test "$missing_status" -eq 5
test "$abi_status" -eq 6

for artifact in "$aarch64_build/libtest_c_identity.so" "$rust_artifact"; do
  readelf -h "$artifact" | grep -q 'Class:.*ELF64'
  readelf -h "$artifact" | grep -q "Data:.*little endian"
  readelf -h "$artifact" | grep -q 'Machine:.*AArch64'
  test -z "$(nm -D --undefined-only "$artifact")"
  ! readelf -dW "$artifact" | grep -Eq '\(NEEDED\)|\(INIT\)|\(INIT_ARRAY\)'
done

printf '%s\n' \
  'AArch64 target: aarch64-linux-gnu / aarch64-unknown-linux-gnu' \
  'Execution: qemu-aarch64 user-mode with Debian GNU sysroot' \
  'Pointer width: 8; size_t width: 8 (compile-time assertions passed)' \
  'C ABI callback and byte-exact vBuf identity: PASS' \
  'Rust ABI callback and byte-exact vBuf identity: PASS' \
  'C and Rust workspace query/range/callback contract: PASS' \
  'Linux /proc/<pid>/fd race-resistant load path under AArch64: PASS' \
  'Missing export, ABI mismatch, dependency, and machine mismatch rejection: PASS'
