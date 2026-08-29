# Native ABI portability qualification

## Status and boundaries

Bloom primitive ABI v1 remains unchanged in semantics and symbol set. The normative calling declaration is [`include/bloom/primitive_abi.h`](../include/bloom/primitive_abi.h); [`primitive-abi-v1.md`](primitive-abi-v1.md) defines its behavior.

Keep these identities separate:

```text
semantic capability  math.argmin.u32@1.0.0
source implementation C, Rust, Zig, ...
C calling ABI        Bloom primitive ABI v1
target artifact      one target-specific ELF/PE/Mach-O binary + hash
persistent data      canonical vBuf
```

The same source and semantic contract may produce several target artifacts. A Linux `.so` is not a Windows `.dll` or macOS `.dylib`, and filenames are locators rather than semantic identities. Registry resolution must use capability identity, target constraints, artifact hash, format, and ABI compatibility.

The current runtime and build remain Linux-only. ABI v1 fixtures now execute on native x86_64 Linux and AArch64 Linux GNU under QEMU user-mode, as documented in [`aarch64-abi-v1.md`](aarch64-abi-v1.md). This does not claim published AArch64 capabilities, native AArch64 hardware performance, PE/Mach-O admission, or Windows/macOS loading.

## ABI-v1 type audit

| ABI use | C type | Classification | Rule |
|---|---|---|---|
| ABI version | `uint32_t` | fixed-width primitive | exact 32-bit unsigned value |
| status/result | `int32_t` | fixed-width primitive | zero success, nonzero failure |
| serialized bytes | `uint8_t` | fixed-width primitive | opaque canonical vBuf bytes |
| input/output address | pointer | target-sized pointer | borrowed under documented lifetime |
| input/output length | `size_t` | platform-sized primitive | target C ABI width and addressability |
| callback/context | function pointer / `void *` | target-sized pointers | opaque context; explicit C calling convention |

No public ABI-v1 value is a C enum, C `bool`, `long`, `wchar_t`, `off_t`, bitfield, compiler-sized aggregate, or language-native rich type. Function pointers are target-ABI values and are never serialized.

### `size_t` decision

Keep `size_t` in ABI v1. These lengths describe an in-process borrowed memory span, not a persistent vBuf count. `size_t` matches C pointer addressability and avoids accepting a `uint64_t` span that cannot be indexed on a 32-bit host. Binary artifacts are already target-specific, so 32-bit and 64-bit pointer/`size_t` layouts are separate artifact targets rather than one interchangeable binary ABI.

Changing to `uint64_t` would create an ABI revision and force every host and artifact to check conversion to native address size without improving cross-target binary interchange: pointers themselves remain target-sized. Persistent counts and offsets remain fixed-width vBuf fields and must be checked before conversion to `size_t`.

Use fixed-width integers for target-independent values such as versions, statuses, flags, serialized counts, and declared resource sizes. Use `size_t` only for a currently addressable native memory span.

## Calling convention and symbol visibility

The header now defines `BLOOM_CALL`. It is explicit `__cdecl` on Windows and the normal C convention elsewhere. The macro is applied to exported functions and the write callback because both sides of a callback must agree. This prevents accidental x86 Windows `stdcall`, `fastcall`, or `vectorcall`; on targets with one effective C convention it is harmless.

C++ consumers remain inside `extern "C"`, preventing C++ name mangling. Rust implementations must use `extern "C"`; Zig and other languages must select the target C ABI. No native Rust, C++, Go, or other language calling convention may cross the boundary.

`BLOOM_EXPORT` is a small implementation visibility helper:

- Windows C/C++ primitive builds define `BLOOM_PRIMITIVE_IMPLEMENTATION` and receive `__declspec(dllexport)`.
- GCC/Clang targets receive default visibility, including when a build otherwise hides symbols.
- unsupported compilers receive an empty fallback and must arrange equivalent export visibility in their build.

Export policy does not identify a capability. The logical ABI symbols remain `bloom_primitive_abi_version` and `bloom_primitive_run_vbuf`; PE, ELF, and Mach-O inspection must verify them according to each format. Rust/Zig implementations may use their language's equivalent unmangled export annotation rather than consuming the C macro.

## Primitive-only boundary rule

Bloom's public native ABI must be expressible using C-compatible fixed-width primitives, pointers with explicit lengths, opaque context/handles, status/version values, and only carefully versioned flat POD structures when unavoidable.

Forbidden boundary values include Rust `Vec`, `String`, references or native slice fat pointers; C++ classes, exceptions, `std::vector`, or virtual interfaces; Python objects; Go slices; trait objects; language `Result` values; and language allocator objects. Such abstractions may exist behind the artifact boundary only.

The header is not an algorithm library, vBuf parser, registry API, planner API, or runtime SDK. vBuf carries capability data; the catalog carries semantic and artifact metadata; the header carries only the native call contract.

## Rules for any future POD structure

No aggregate is needed by ABI v1. If a future feature cannot remain individual primitive arguments, a public flat POD must:

1. begin with explicit fixed-width `struct_size` and ABI/version fields;
2. use fixed-width integer fields and explicit pointer-plus-length pairs;
3. avoid C enums, `bool`, bitfields, flexible arrays, nested ownership, and compiler-specific packing;
4. use explicit reserved fields that writers zero and readers validate or ignore as specified;
5. define ownership, mutability, alignment, and lifetime for every pointer;
6. permit append-only tail extension through `struct_size` negotiation;
7. reject undersized required prefixes and ignore only documented unknown tails;
8. document `sizeof`/`offsetof` expectations per supported target ABI and test them from each language binding;
9. avoid `#pragma pack`; natural alignment plus explicit fields is safer than unaligned packed access;
10. never use compiler object layout as persistent vBuf encoding.

The implemented argsort workspace uses a host-owned mutable byte range (`uint8_t *` plus native span size) established by the separately versioned invocation contract; it does not use a general language allocator object.

## Rust implementation qualification

A Rust capability can implement ABI v1 with unmangled `extern "C"` exports and C-compatible boundary types:

```text
u32 / i32
*const u8 / *mut c_void
usize for C size_t
Option<extern "C" fn(...)> for a nullable C callback
```

Internally it may establish checked slices, use safe indexing, and return internal Rust `Result` values, but it must translate all outcomes to ABI status and callback behavior. Rust references, slices as Rust ABI values, vectors, strings, trait objects, panic payloads, and allocators do not cross.

No panic may unwind across Bloom's C ABI. Production options depend on the target and dependency policy: build with aborting panic semantics, or contain unwind inside Rust only where the target/runtime supports that without crossing the ABI. An exported function must translate caught failures to status. C++ exceptions and other language exceptions follow the same invariant. Destructors or cleanup must complete on the implementation side.

The test-only Rust fixture is `no_std`, uses `panic=abort`, and has no panic-producing execution path. Its required no-std panic handler is non-returning. This proves call compatibility, not a complete production Rust primitive template.

## Runtime and dependency implications

Rust does not automatically produce a dependency-free native artifact. A normal `std` `cdylib` may import libc, compiler unwind support, platform APIs, or initialization/finalization machinery. Windows and macOS toolchains may require expected platform loader/runtime imports even when no capability dependency is intended.

The test fixture demonstrated this distinction on Linux:

- default Rust `cdylib` linking introduced CRT initializer/finalizer entries and weak unresolved imports;
- `no_std`, `panic=abort`, `-nostdlib`, and `--no-undefined` produced an artifact accepted by the unchanged pure Linux policy;
- the admitted fixture has no `DT_NEEDED`, dynamic initializers, or unresolved imports.

Do not generalize that result to arbitrary Rust algorithms or targets. Dependency policy is target- and format-specific. Future admission should distinguish explicitly allowed platform loader/runtime imports from undeclared capability dependencies, record them in artifact metadata, and inspect PE/Mach-O with native format tooling. Current Linux pure-artifact rejection remains unchanged. Import inspection is admission policy, not a sandbox; dependency-free native code can still execute syscalls.

Implementation-language heap facilities are not a Bloom workspace contract. C `malloc`, Rust global allocation, or direct OS allocation would bypass host resource ownership for `math.argsort.u32`; host-controlled invocation-scoped workspace remains separately required.

## Cross-language fixture

`tests/fixtures/rust_identity` is a test-only Rust `cdylib`. It exports only the logical ABI-v1 behavior needed for identity and is not a catalog capability. CMake builds it with the existing Cargo prerequisite and Linux pure-artifact linker policy. The normal Bloom path then:

```text
checked temporary catalog
→ unchanged native admission
→ ctypes/dlopen loader
→ public ABI v1
→ Rust extern-C artifact
→ byte-identical validated vBuf
```

The runtime contains no Rust-specific branch. This is the desired compatibility proof.

Build/inspection commands are:

```bash
cmake -S . -B build -G Ninja
cmake --build build
ctest --test-dir build --output-on-failure

readelf -dW build/rust-fixtures/debug/libbloom_test_rust_identity.so
nm -D --undefined-only build/rust-fixtures/debug/libbloom_test_rust_identity.so
```

## Small shared ABI package

The current header plus normative ABI document are the nucleus of a future small `bloom-abi` package. Extract it only when a second repository or independent producer needs versioned consumption. A suitable package contains:

```text
include/bloom/primitive_abi.h
ABI.md
cross-language compile/load tests
canonical vBuf conformance inputs and expected outputs
small generated or reviewed language declarations
```

The C-compatible declaration remains normative. A Rust helper crate or Zig declarations mirror it and are tested against symbol, calling, size, and behavior fixtures; they do not redefine the ABI. Keep registry clients, algorithms, vBuf parsers, transport, allocation policy, and runtime internals out. Do not create a broad SDK prematurely.

## Cross-platform build and validation matrix

The qualified and future isolated build matrix is:

```text
x86_64-linux-gnu          ELF    .so  verified natively, C and Rust
AArch64 Linux GNU         ELF    .so  verified under QEMU, C and Rust
x86_64-windows-msvc       PE     .dll future
AArch64 macOS             Mach-O .dylib future
```

For every target:

1. build from an exact source revision and locked toolchain/dependencies;
2. run language ABI compile checks and target-specific symbol inspection;
3. inspect format, machine, dependencies/imports, and initializer policy;
4. load only through the public ABI in a matching target worker;
5. run malformed-input, ABI-mismatch, effect-denial, and ownership tests;
6. run the same canonical vBuf semantic fixtures;
7. require byte-identical canonical output for deterministic capabilities;
8. hash and publish each physical artifact independently with target metadata.

Cross-compilation alone does not prove load compatibility; contract tests must execute on the target ABI. Machine code and hashes are expected to differ. Capability name and contract version remain platform-neutral.

## Current portability risks

- Runtime admission understands only ELF64 little-endian Linux; EM_X86_64 and EM_AARCH64 are verified, and inspection uses `readelf`.
- Validated loading relies on Linux `/proc/<pid>/fd`; Windows/macOS need different race-resistant load binding.
- CMake rejects non-Linux systems and uses ELF/GNU linker options such as `-nostdlib` and `--no-undefined`.
- The target model currently has no PE/Mach-O dependency or initializer policy.
- `ctypes.CDLL` loading is wrapped by Linux-specific admission despite ctypes itself supporting other platforms.
- ABI v1 intentionally varies pointer and `size_t` width by target architecture.
- Rust `cdylib` dependency shape varies with target, standard library use, panic strategy, and linker configuration.
- The current ABI has no host-owned count-proportional workspace contract.

These are target artifact/runtime implementation gaps, not reasons to put platform or implementation language into semantic capability names or vBuf.

## Narrowest next step

Run the existing AArch64 lane on a native AArch64 Linux GNU worker and attach it to CI when CI infrastructure exists. The emulated lane already tests pointer/`size_t`, machine metadata, target naming, callbacks, and byte-exact C/Rust behavior; native execution removes emulation as the remaining architecture qualification caveat. Workspace ABI design remains a separate capability-driven step.
