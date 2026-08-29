# AArch64 Linux ABI v1 execution qualification

## Verified scope

Bloom primitive ABI v1 was executed for two implementation languages on one concrete second architecture:

```text
C compiler target:    aarch64-linux-gnu
Rust compiler target: aarch64-unknown-linux-gnu
artifact target name: aarch64-linux-gnu
OS / format / endian: Linux / ELF64 / little-endian
```

This is AArch64 Linux GNU ABI compatibility, not generic ARM, big-endian ARM, Android, musl, or native hardware qualification. The artifacts are test fixtures and are not catalog-published production capability artifacts.

The host was x86_64 Debian Linux. Execution used QEMU 10.0.11 user-mode with a Debian GNU AArch64 sysroot inside an isolated Docker toolchain container. Native AArch64 ABI instructions, dynamic loading, function calls, pointers, and callbacks executed under emulation; no hardware-performance conclusion is possible.

## Build and execution lane

The default host build remains unchanged. The optional CMake target is:

```bash
rustup target add aarch64-unknown-linux-gnu
cmake -S . -B build -G Ninja
cmake --build build
cmake --build build --target aarch64_abi_test
```

The target:

1. cross-builds the existing `no_std` Rust fixture with Rust `aarch64-unknown-linux-gnu` and bundled `rust-lld`;
2. builds a pinned Debian container containing GCC `aarch64-linux-gnu`, GNU binutils, the GNU sysroot, Python, and `qemu-aarch64`;
3. cross-builds the C fixture and an AArch64 ABI runner from the public header;
4. applies Bloom's existing ELF admission implementation to C and Rust artifacts;
5. executes both artifacts under explicit QEMU user-mode;
6. compares each output byte-for-byte with the same authoritative vBuf v0.6 fixture used on x86_64;
7. executes negative symbol/version tests and admission dependency/machine tests.

Docker is required only for this optional lane. No CI configuration existed, so no broad CI framework was added.

## Public ABI and native widths

ABI version remains:

```text
0x00010000
```

No public header, calling signature, status, callback, ownership, or vBuf representation changed for this qualification. AArch64 fixture compile-time assertions established:

```text
sizeof(void *) = 8
sizeof(size_t) = 8
```

Equivalent Rust compile-time checks established `usize` and data pointers are eight bytes for `target_arch = "aarch64"`. This is the tested LP64 target result, not a new fixed-width ABI rule. `size_t` remains target-native.

The AArch64 runner invokes both required symbols and passes a real `extern C`/`BLOOM_CALL` output callback. Both the C and Rust artifacts return the complete borrowed input through that callback, proving pointer, `size_t`, function-pointer, and context interoperability.

## Canonical vBuf parity

Both AArch64 fixtures consume:

```text
../vBuf/tests/fixtures/v06/valid-basic.vbuf
```

Required comparisons are:

```text
canonical input == AArch64 C output
canonical input == AArch64 Rust output
AArch64 C output == AArch64 Rust output
```

All comparisons pass byte-for-byte. The existing x86_64 C and Rust fixtures use the same input and also produce it byte-for-byte, so parity across both language and architecture dimensions is established for identity semantics. No architecture-specific expected output exists.

## ELF admission

No admission source change was required. `src/bloom/artifact.py` already defines the narrow Linux mappings:

```text
x86_64  → EM_X86_64 (62)
aarch64 → EM_AARCH64 (183)
```

The same code verifies ELF64, little-endian data, `ET_DYN`, target machine, required exports, dependencies, initializers, and unresolved imports. Host GNU `readelf` correctly inspects foreign AArch64 ELF, so no target-prefixed policy or parser was added.

The lane computes SHA-256 identities and exercises full artifact validation with an explicit AArch64 host-target context before execution. It also verifies:

- the real x86_64 host rejects an AArch64 target mapping;
- an AArch64 target context rejects the existing x86_64 artifact mapping;
- direct ELF machine checks reject either artifact under the other architecture target;
- an AArch64 artifact with a deliberate libc dependency is rejected;
- missing exports and reported ABI mismatch fail in the executed AArch64 runner.

Target mismatch remains a pre-load failure; no implicit emulation is part of Bloom runtime policy.

## Rust artifact inspection

The AArch64 Rust fixture retains:

```text
no_std
panic = abort
rust-lld direct linking
--no-undefined
```

Direct `rust-lld` linking supplies the same effective no-CRT/no-stdlib behavior as the x86_64 fixture's `-nostdlib` linker argument. Inspection reports:

```text
Class:       ELF64
Data:        little-endian
Type:        ET_DYN shared object
Machine:     AArch64
Exports:     bloom_primitive_abi_version
             bloom_primitive_run_vbuf
Undefined:   none
DT_NEEDED:   none
DT_INIT:     none
DT_INIT_ARRAY: none
```

The C fixture has the same admission properties. No architecture support symbol or dependency required a policy exception.

## Linux race-resistant load path

The AArch64 runner opens each artifact and calls `dlopen` through:

```text
/proc/<pid>/fd/<open-fd>
```

under QEMU AArch64 execution. This confirms the existing race-resistant path is a Linux OS mechanism and does not need architecture-specific handling. The runner does not replace Bloom's runtime; it isolates the native load/call boundary while exercising the same path shape.

## Negative-test qualification

Verified in the AArch64 lane:

- C and Rust artifacts pass existing physical admission;
- x86_64/AArch64 machine and target mismatches are rejected;
- missing required export is rejected by the executing runner;
- incompatible reported ABI is rejected by the executing runner;
- unexpected dynamic dependency is rejected by Bloom admission;
- required callback invocation succeeds for both languages;
- frozen workspace query/run exports execute for both languages with 8-byte alignment and 64-bit spans.

Malformed vBuf rejection before primitive execution remains covered by the normal Bloom runtime tests on x86_64. The optional AArch64 runner intentionally tests only the public native ABI and does not duplicate authoritative vBuf Core validation. It now also executes the test-only C and Rust workspace fixtures, covering the frozen query, exact/oversized/undersized range, alignment, callback-failure, and zero-range rules. A complete AArch64 Bloom runtime worker, including AArch64 Python and vBuf Core, has not been executed; therefore architecture-specific end-to-end runtime validation is not claimed.

## Matrix result

| Architecture | C fixture | Rust fixture | Environment |
|---|---:|---:|---|
| x86_64 Linux GNU | PASS | PASS | native host |
| AArch64 Linux GNU | PASS | PASS | QEMU user-mode |

This validates ABI behavior under emulation, not physical AArch64 performance or production publication.

## Remaining limitations

- AArch64 artifacts are test-only and are not in the production catalog.
- No native AArch64 hardware or full Bloom Python/vBuf runtime worker was exercised.
- The optional lane currently requires Docker, network access to construct its toolchain image, and the Rust AArch64 standard component.
- Only Linux GNU ELF64 little-endian is covered; musl, Android, big-endian, PE, and Mach-O remain unverified.
- The Docker/sysroot toolchain and host Rust toolchain are separate build inputs and must be pinned more fully before publication provenance.
- The unresolved argsort workspace boundary remains separate and unchanged.

## Narrowest next step

Run the same `aarch64_abi_test` semantics on a native AArch64 Linux GNU worker, then add the lane to existing CI when CI infrastructure exists. This removes emulation as the remaining ABI-execution qualification gap before returning to workspace ABI design.
