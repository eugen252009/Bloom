# Bloom native primitive ABI v1

## Scope

ABI v1 is the minimum calling boundary needed to load one bounded, pure native transformation. It is intentionally not a general plugin framework and does not define the persistent vBuf representation. Its fixed run export executes one behavior per artifact, which is sufficient for the implemented `bytes.identity`, `math.min.u32`, and `math.argmin.u32` artifacts but is not a general multi-capability artifact mechanism.

The authoritative declaration is [`include/bloom/primitive_abi.h`](../include/bloom/primitive_abi.h). Its portability audit and language rules are in [`native-abi-portability.md`](native-abi-portability.md); executable C/Rust qualification for AArch64 Linux GNU is in [`aarch64-abi-v1.md`](aarch64-abi-v1.md).

ABI v1 uses fixed-width `uint32_t`/`int32_t` values for versions and statuses, `uint8_t` for serialized bytes, target pointers, and `size_t` for currently addressable native spans. `BLOOM_CALL` fixes `__cdecl` on Windows and the target C convention elsewhere; it applies to exports and callbacks. `BLOOM_EXPORT` is a visibility helper, not semantic identity. C++ name mangling and all language-native calling conventions or exceptions are forbidden at the boundary.

## Required exports

```c
BLOOM_EXPORT uint32_t BLOOM_CALL bloom_primitive_abi_version(void);

BLOOM_EXPORT int32_t BLOOM_CALL bloom_primitive_run_vbuf(
    const uint8_t *input,
    size_t input_size,
    bloom_primitive_write_fn write,
    void *write_context);
```

`bloom_primitive_abi_version` returns `0x00010000` for this ABI. The first runtime accepts only this base version. Capability/feature negotiation remains future work; exact equality is current behavior, not a commitment to permanent lockstep minor versions.

The runtime validates one complete vBuf through authoritative vBuf Core before calling `bloom_primitive_run_vbuf`. `input` is a bounded borrowed byte span valid only for the call. It remains canonical serialized vBuf data; the C pointer/length pair is not its wire definition.

Output is emitted through:

```c
typedef int32_t (BLOOM_CALL *bloom_primitive_write_fn)(
    void *context,
    const uint8_t *data,
    size_t size);
```

Callback bytes are borrowed for that callback invocation. The callback consumes or copies them synchronously. Nonzero callback or primitive status means failure. No allocation crosses the ABI, and no Bloom runtime-private type or symbol is exposed.

This one-shot ABI materializes input. Opaque configure/process/finalize state and incremental orchestration are deliberately deferred until a real streaming primitive requires them.

The [`math.argsort.u32` qualification](math-argsort-u32-qualification.md) identified a concrete ABI-v1 limit: a pure artifact cannot obtain realistic count-proportional mutable workspace from immutable input and an append-only write callback. Unbounded stack allocation, fixed static buffers, direct OS allocation, forbidden allocator imports, and pathological repeated-scan algorithms are not accepted substitutes. The separately versioned invocation-scoped host-owned pre-sized scratch-range contract is specified in [`workspace-abi-spec.md`](workspace-abi-spec.md) and integrated for explicitly bound capabilities; the selected qualification rejects a general allocator and public `free()`, and ABI v1 is unchanged. No production semantic workspace capability is registered.

ABI v1 remains valid unchanged for its implemented one-capability artifacts. It does not establish that semantic capabilities and physical artifacts must always have 1:1 cardinality.

## Future multi-capability direction

The registry must remain authoritative: it resolves a semantic capability to an expected artifact before admission or native execution. A future runtime descriptor may verify that the admitted artifact provides the expected capability; Bloom should not discover capabilities by loading arbitrary `.so` files.

Three calling models remain possible:

- **Separate exported symbols:** easy to inspect statically and call directly, but grows the public symbol surface and requires stable collision-free naming and per-symbol version rules.
- **Versioned descriptor/function table:** keeps a small exported surface and permits verification plus independently callable entries, but requires careful C layout, bounds, lifetime, and compatibility design.
- **Generic dispatch by capability ID:** keeps the smallest function surface, but carries capability-ID semantics across the ABI and weakens static separation and per-entry verification.

When a concrete bundled artifact is required, the leading direction is a versioned descriptor/function table reached through one stable artifact-level export, with capability names and contracts still owned by the registry. This is a recommendation, not an implemented ABI or finalized layout; IDs, structs, negotiation, and ownership must be specified and compatibility-tested at that time.

Artifact packaging may change without changing capability identity. A capability must remain independently addressable and must not acquire semantic dependencies on sibling entries merely because they share a binary. Runtime reuse of an already loaded bundle is only an execution optimization and must not influence semantic selection without established equivalence.

Bundling may reduce tiny shared-library count, `dlopen` operations, duplicated optimized helpers, catalog/artifact management overhead, and distribution overhead. A future download of one bundle may satisfy several registry-known capability mappings, but downloading it must not discover, register, or activate undeclared capabilities.

## Validation and trust

The current pure-native admission check verifies the manifest hash and target, ELF type/machine, required exports, reported ABI version, and rejects dynamic dependencies, initializer entries, and unresolved imports.

Native import/dependency validation is a publication/admission check, not a security boundary. Native execution currently occurs in the CLI process and is suitable only for locally trusted artifacts.

For a future bundle, the admission boundary is the whole physical artifact while each capability remains a semantic contract boundary. Capabilities may share a binary only when their trust, effects, host imports, dependencies, and execution/isolation requirements are compatible. An artifact containing an effectful capability cannot be admitted as pure merely by selecting a different entry.
