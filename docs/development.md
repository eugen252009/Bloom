# First vertical slice development

## Prerequisites

The current implementation targets Linux and uses Python 3.11+, a C compiler, CMake, Cargo, `readelf`, and `nm`. It integrates with authoritative vBuf Core rather than implementing another wire parser.

Keep the vBuf checkout beside Bloom, or set `VBUF_ROOT` explicitly:

```text
projects/
├── Bloom/
└── vBuf/
```

The required vBuf checkout must provide `rust/Cargo.toml`, the `vbuf-core` package, and its v0.6 conformance fixtures.

## Build and local registration

```bash
cmake -S . -B build -G Ninja
cmake --build build
```

The build compiles vBuf Core, `libbytes_identity.so`, `libmath_min_u32.so`, `libmath_argmin_u32.so`, and `libmath_argsort_u32.so`, plus test-only malformed/failing/workspace C artifacts and test-only `no_std` Rust identity/workspace artifacts. It generates algorithm fixtures through the authoritative vBuf writer, hashes all four registered catalog capability artifacts, and creates the checked local catalog at `build/catalog.json`. Workspace compatibility fixtures are never registered; `math.argsort.u32` is the first production workspace capability. The Rust artifact is not registered; tests admit and execute it through a temporary `bytes.identity` catalog mapping to prove that the runtime has no implementation-language dependency. Catalog creation is local availability, not publication or remote activation.

To regenerate the catalog explicitly after rebuilding the artifacts:

```bash
python3 scripts/register_artifact.py \
  --capability primitives/bytes.identity/manifest.template.json \
               build/primitives/libbytes_identity.so \
  --capability primitives/math.min.u32/manifest.template.json \
               build/primitives/libmath_min_u32.so \
  --capability primitives/math.argmin.u32/manifest.template.json \
               build/primitives/libmath_argmin_u32.so \
  --output build/catalog.json \
  --target x86_64-linux-gnu
```

Use the actual current-host target when it differs.

## Test

```bash
ctest --test-dir build --output-on-failure
```

Tests load primitives as external `.so` files; the runtime does not link their implementations. The cross-language fixture is built and inspected under the unchanged Linux pure-artifact policy:

```bash
readelf -dW build/rust-fixtures/debug/libbloom_test_rust_identity.so
nm -D --undefined-only build/rust-fixtures/debug/libbloom_test_rust_identity.so
```

The portable ABI qualification is documented in [`native-abi-portability.md`](native-abi-portability.md).

## Optional AArch64 Linux ABI lane

The same C ABI fixture and test-only Rust fixture are executable for the concrete GNU targets `aarch64-linux-gnu` and `aarch64-unknown-linux-gnu`. The locally verified environment uses explicit `qemu-aarch64` user-mode execution with a Debian GNU sysroot in Docker; this is ABI execution under emulation, not native-hardware or performance qualification.

Prerequisites are Docker plus the Rust target component:

```bash
rustup target add aarch64-unknown-linux-gnu
cmake -S . -B build -G Ninja
cmake --build build
cmake --build build --target aarch64_abi_test
```

This optional target is separate from the default host test suite. It cross-builds the existing identity fixtures plus the test-only workspace Rust fixture, builds the C workspace fixture and runner in the lane, applies existing ELF admission checks, invokes real AArch64 callbacks through `/proc/<pid>/fd` loading, compares identity output byte-for-byte with the existing canonical vBuf fixture, and exercises the frozen workspace query/range/alignment/callback contract. It also tests machine, dependency, symbol, and ABI-version rejection. Exact scope and limitations are documented in [`aarch64-abi-v1.md`](aarch64-abi-v1.md).

## Use

```bash
./build/bloom capabilities
./build/bloom describe bytes.identity
./build/bloom describe math.min.u32
./build/bloom describe math.argmin.u32
./build/bloom describe math.argsort.u32
cat ../vBuf/tests/fixtures/v06/valid-basic.vbuf \
  | ./build/bloom run bytes.identity \
  > output.vbuf
cmp ../vBuf/tests/fixtures/v06/valid-basic.vbuf output.vbuf

cat build/fixtures/math.min.u32/normal-input.vbuf \
  | ./build/bloom run math.min.u32 \
  > minimum.vbuf
cmp build/fixtures/math.min.u32/normal-expected.vbuf minimum.vbuf

cat build/fixtures/math.argmin.u32/normal-input.vbuf \
  | ./build/bloom run math.argmin.u32 \
  > index.vbuf
cmp build/fixtures/math.argmin.u32/normal-expected.vbuf index.vbuf

./build/bloom --max-workspace-bytes 1048576 run math.argsort.u32 \
  < build/fixtures/math.argsort.u32/normal-input.vbuf \
  > argsort.vbuf
cmp build/fixtures/math.argsort.u32/normal-expected.vbuf argsort.vbuf
```

`bloom run` reserves stdout for primitive bytes and sends diagnostics to stderr. Workspace execution is disabled unless `--max-workspace-bytes N` is supplied (or `BLOOM_MAX_WORKSPACE_BYTES` is set); this affects only capabilities with an explicit workspace execution binding and does not affect ABI-v1 capabilities. The wrapper has no terminal or PTY dependency, so it can later be placed on an SSH host's `PATH` and invoked with `ssh -T host bloom ...`.

## Catalog schema v1

The checked JSON root contains `schema_version: 1` and a `capabilities` array. Each entry currently requires:

- capability `name`, `contract_version`, and local `available` state;
- artifact `format`, SHA-256 `identity`, path, target, and primitive ABI base;
- input/output representations;
- determinism and declared effects;
- input/output streaming, materialization, and output-start behavior.

The implemented catalog is deliberately local and exact-name based. It does not download, publish, activate, synchronize, or semantically search artifacts.

In schema v1, `format`, SHA-256 `identity`, `path`, `target`, and `bloom_primitive_abi` are artifact-level properties. `name`, `contract_version`, `input`, `output`, `deterministic`, `effects`, and `streaming` describe the semantic capability. `available` describes the local capability-to-artifact resolution state rather than an intrinsic property of either identity.

The exact implemented primitive contracts are documented in [`math-min-u32.md`](math-min-u32.md) and [`math-argmin-u32.md`](math-argmin-u32.md). [`math-argsort-u32-qualification.md`](math-argsort-u32-qualification.md) records why count-proportional stable sorting is not registered under ABI v1. [`workspace-qualification.md`](workspace-qualification.md) selects a single pre-sized host-owned range, rejects public `free()` and a general allocator for the first consumer, and [`workspace-abi-spec.md`](workspace-abi-spec.md) freezes the separately versioned query/execution boundary and compatibility-test matrix. Only test-only fixtures exercise it as semantic capabilities; the loader/runtime integration is production code, while no production workspace capability is registered.

The current schema nests an artifact record in each capability entry. It does not forbid two entries from containing the same artifact identity and path, but would duplicate that metadata; the current ABI also has only one fixed run entrypoint. No bundled-artifact execution is therefore claimed. If a real bundle is introduced, a later checked schema may normalize shared artifact records and expected `provides` bindings, while preserving independent capability contracts and registry-first discovery.
