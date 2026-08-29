# Workspace execution ABI specification

## Status and maturity

This document freezes the workspace execution contract. Its loader, admission, catalog binding, budget, and runtime path are production-integrated, but only test-only C/Rust fixtures exercise it; no production semantic workspace capability has been added. No ABI-v1 symbols or production workspace symbols are declared in the public v1 header.

- **Frozen for compatibility testing:** public names, version, signatures, and semantic rules exercised by the test-only fixtures.
- **Proposed:** the runtime/catalog integration shape, which is not implemented.
- **Deferred:** intentionally open design work that must not be inferred from incidental code.

The proving consumer is the unimplemented `math.argsort.u32`. Existing workspace-free capabilities continue to use ABI v1 unchanged.

## 1. Recommendation

### Versioning models considered

#### Model A: replacement ABI

A workspace artifact would expose a new run signature and ABI v2 would replace ABI v1 for that artifact.

Rejected as the primary architecture. It needlessly makes workspace-free primitives participate in a larger contract, duplicates the existing input/output semantics, complicates admission and compatibility, and encourages treating a resource extension as a universal ABI generation. ABI v1 artifacts must remain loadable without recompilation.

#### Model B: optional separately versioned execution feature

An artifact may expose the existing ABI v1 surface and an explicitly advertised workspace execution surface. The runtime selects one surface from capability metadata before invocation.

This preserves the simple path and is suitable for the first implementation.

#### Model C: distinct execution ABI family

The base calling ABI and workspace execution contract have independent version identities:

```text
base calling ABI version       !=       workspace execution ABI version
```

This accurately models workspace as an orthogonal execution resource rather than a replacement for v1. It also leaves room for later execution features without assigning unrelated meanings to the base ABI version.

### Selected architecture

**Model C, delivered through Model B's opt-in exports, is recommended.**

The catalog capability declares that it requires a named workspace execution family and version. Admission then verifies the expected exports in the physical artifact. A workspace-free capability declares the existing base execution and requires neither the query nor workspace run export.

The workspace family version is frozen for compatibility testing as:

```c
#define BLOOM_PRIMITIVE_WORKSPACE_ABI_VERSION ((uint32_t)0x00010000u)
```

It is independent of `BLOOM_PRIMITIVE_ABI_VERSION` and does not mean that ABI v1 has been replaced. As with the base ABI, this version is currently matched exactly; major/minor compatibility negotiation is deferred.

This design does not require one artifact to provide only one capability. A future descriptor can bind several semantic capabilities to several run/query pairs while preserving the same independent version identities.

## 2. Concrete calling shape

### Proposed direct functions

The first implementation should use primitive arguments rather than a struct:

```c
BLOOM_EXPORT uint32_t BLOOM_CALL
bloom_primitive_workspace_abi_version(void);

BLOOM_EXPORT int32_t BLOOM_CALL
bloom_primitive_workspace_required(
    const uint8_t *input,
    size_t input_size,
    size_t *required_size,
    size_t *required_alignment);

BLOOM_EXPORT int32_t BLOOM_CALL
bloom_primitive_run_vbuf_workspace(
    const uint8_t *input,
    size_t input_size,
    uint8_t *workspace,
    size_t workspace_size,
    bloom_primitive_write_fn write,
    void *write_context);
```

These names are **frozen for compatibility testing**. They are deliberately capability-neutral: `workspace` describes an execution contract, not argsort or any other semantic capability. A future descriptor can bind these operations to a capability without changing their resource semantics.

Alternatives evaluated:

- **A. Additional pointer and length parameters:** selected. It is the smallest C-compatible shape and keeps the existing callback and span conventions visible.
- **B. Flat versioned execution descriptor:** deferred. It would be useful only once negotiated flags, multiple views, or several optional services are demonstrated. It introduces struct size, alignment, reserved fields, and lifetime compatibility immediately.
- **C. Separate workspace descriptor argument:** rejected for the first version. A two-field descriptor does not solve a demonstrated problem that two parameters do not solve; it hides the contract without reducing it.

No allocator callbacks, `free`, handles, host-service table, exceptions, language-native objects, or persistent ownership cross this boundary.

### Function relationship

The workspace run function has the same input and output callback semantics as v1, plus one mutable range. It is not a fallback or replacement implementation of `bloom_primitive_run_vbuf`.

A workspace-capable artifact may optionally retain a v1 implementation for a separate workspace-free capability, but the runtime must not silently call the v1 function for a capability whose contract requires workspace.

## 3. Workspace semantics

### Required ownership and lifetime

The host owns the range. The range is borrowed by the primitive only during the dynamic extent of `bloom_primitive_run_vbuf_workspace`:

```text
host reserves
→ primitive borrows and mutates
→ primitive returns
→ host reclaims
```

Required rules:

- `workspace` points to host-owned mutable storage or is null only under the zero-size rule below;
- the primitive may write only within `[workspace, workspace + workspace_size)`;
- the primitive may partition the range internally;
- the primitive must not transfer ownership or call a release operation;
- the primitive must not retain any workspace address after return;
- the host must not reclaim, reuse, or concurrently expose the range before return;
- release is implicit at invocation end;
- there is no public `free` and no general allocator;
- no workspace pointer may be returned through output, global state, a callback context, a thread, or an opaque handle.

The range is temporary runtime representation. It is not persistent vBuf data and must not be serialized into the output.

### Nullability and zero length

The exact rule is:

```text
workspace == NULL && workspace_size == 0
```

is a valid representation of an empty range. A non-null zero-length pointer is also valid. A null pointer with nonzero size is invalid and must be rejected before primitive execution.

A capability whose required size is zero may accept either representation. A capability requiring any positive size must receive a non-null pointer and sufficient size. The query itself may receive a null input only when `input_size == 0`; such input will normally fail the Core-validated-input precondition before the query is called.

`input == NULL` with nonzero `input_size` is invalid. `write == NULL` is invalid for every execution call, including calls that would otherwise emit no bytes. `write_context` is opaque and may be null.

### Callback, input, and workspace lifetime

For the entire execution call, the primitive may borrow:

- the input span;
- the workspace span;
- the synchronous output callback;
- the output callback context.

All four become invalid to the primitive after return. The primitive must not retain or invoke any of them asynchronously. Callback data remains borrowed only for each callback invocation, as defined by ABI v1.

## 4. Alignment

The workspace execution family guarantees a minimum starting alignment of **8 bytes** for a non-empty range. This is an ABI contract, not an allocator accident, and is sufficient for the immediate argsort u64 arrays on the qualified targets.

`required_alignment` is returned by the query as a power of two and must be at least 1. For argsort it is exactly 8, including for an empty input whose required size is zero. The runtime must provide a range whose starting address is aligned to the returned value when the size is nonzero; for a zero-size range, the null/zero representation is valid and no address alignment is required.

The first family does not provide SIMD-specific 16/32/64/128-byte guarantees. A future capability may report a stronger power-of-two alignment if its contract genuinely requires it; that requirement must be declared and bounded before allocation.

Internal partition offsets must be checked. If a primitive requires alignment within the range, it must use checked padding and ensure the padded subrange remains inside `workspace_size`. The host does not provide hidden over-allocation, and the primitive may not shift the pointer outside the supplied range.

Alignment is an ABI property of the invocation, not a manifest expression and not a query for the host to guess. A query result with invalid alignment (zero, non-power-of-two, or unrepresentable) is a query contract failure.

## 5. Workspace query

### Recommendation

A query export is **required for the first general implementation**. Static metadata alone cannot derive `count` through the current runtime API, and teaching the host argsort's semantic layout would couple runtime policy to primitive logic. A fixed budget alone cannot distinguish a safe exact reservation from an insufficient one.

The query is not an algorithm execution pass. It computes only the required range size and alignment.

### Query contract

The query:

- receives a borrowed input span;
- receives raw bytes that the host has already accepted through authoritative vBuf Core validation;
- may inspect and defensively validate only the capability-specific shape it needs;
- may not allocate workspace or any other unbounded memory;
- may not emit output or invoke a callback;
- may not access filesystem, network, clock, randomness, process, or other external effects;
- must be deterministic for identical input bytes;
- must not modify input bytes;
- must write both result outputs only on success;
- must return a nonzero status on malformed capability shape, overflow, invalid pointers, or invalid output parameters.

The query may parse the narrow capability view needed to find `n`; it must not replace or duplicate the full vBuf Core validator. The trust boundary is:

```text
Core structural validity       → host
capability-specific shape/count → query and execution primitive
```

For `math.argsort.u32`, the query checks the single-block unsigned-u32-array contract and calculates:

```text
required_size      = checked(n × 16)
required_alignment = 8
```

The query must not run the sort, allocate a permutation, produce a result, or invoke the output callback. `required_size` and `required_alignment` must both be non-null; either null output pointer is an invalid-argument failure, including when the required size is zero. On any query failure, both output values are set to zero and must be ignored. The execution function performs its own narrow shape and range checks because the ABI cannot assume that every caller is the current Bloom runtime.

### Why not the other sizing options?

- **Manifest/static bound:** useful as declarative metadata and admission information, but insufficient alone when the bound depends on validated input count. A future schema may carry a reviewed rule such as `bytes_per_element: 16`, but the runtime still needs a generic way to obtain the count and must not implement argsort semantics.
- **Fixed runtime budget only:** provides policy but not a required-size calculation. It causes either over-allocation or late insufficient-workspace failure and cannot support exact preflight.
- **Capability-specific host knowledge:** leaks semantic layout and algorithm assumptions into the runtime and prevents clean reuse by future primitives.
- **Query export:** keeps capability-specific sizing beside capability-specific logic, while the host retains allocation policy.

A future generic validated-view API could replace the raw-byte count extraction if vBuf Core exposes that capability. That is deferred and is not required to define this boundary.

## 6. Lifecycle and ordering

The required runtime sequence is:

```text
resolve semantic capability
→ admit artifact and expected execution family
→ load the admitted artifact
→ validate complete input with authoritative vBuf Core
→ call pure workspace query
→ checked result and runtime budget check
→ host reserves aligned range
→ call workspace execution
→ synchronously emit output
→ return from native call
→ reclaim workspace
```

The query must not be used to run the algorithm twice. Contract-specific shape failure may be reported by the query before allocation; execution must repeat only the narrow defensive checks needed to protect its own memory and output invariants.

If query, admission, budget, or allocation fails, the workspace run export must not be called.

## 7. Checked arithmetic and budgets

The persistent vBuf count and native span size are different domains. A fixed-width vBuf count may exceed host addressability and must not be cast to `size_t` until checked.

All of the following are mandatory checked operations:

```text
count representation → size_t
count × bytes_per_element
subrange offset + subrange length
alignment padding calculation
padded offset + requested length
required size → configured budget type / size_t
```

The implementation must reject rather than wrap. Equivalently, each multiplication `a × b` requires `a == 0 || b <= MAX / a`; each addition `a + b` requires `a <= MAX - b`. Alignment rounding must use checked arithmetic, not wrapping masks.

The runtime owns policy:

```text
required workspace  !=  approved workspace
```

The runtime may reject when `required_size` exceeds the configured invocation workspace limit. Equality with the limit is allowed. It must reserve exactly the required size or an explicitly documented larger bounded range; over-allocation must still be charged against the same limit.

The primitive must not choose or override the limit. A supplied range smaller than the query result is an execution contract failure and must be rejected before algorithm work or output.

## 8. Status and failure ownership

The existing ABI v1 `int32_t` result convention remains the type convention, but v1 status meanings must not be mutated. The workspace-family fixture freezes the smallest native status set needed for this contract:

```text
0  OK
1  INVALID_ARGUMENT
3  UNSUPPORTED_SHAPE
4  INSUFFICIENT_WORKSPACE
5  MISALIGNED_WORKSPACE
```

These statuses describe primitive/query contract failures only. Runtime budget denial, host allocation failure, admission failure, and ABI mismatch remain host-side errors and are not returned by the primitive.

The ownership split is:

| Failure | Owner and timing |
|---|---|
| unsupported base/workspace family or missing expected export | admission/loader before invocation |
| invalid Core input | runtime before query |
| capability-specific shape failure | query or primitive, before output |
| required-size overflow or invalid query result | query, then runtime rejection |
| workspace over budget | runtime policy before execution |
| host allocation failure | runtime before execution |
| null/misaligned/too-small supplied range | runtime or primitive boundary check before output |
| algorithm failure | primitive status during execution |
| callback failure | runtime callback bridge; native call returns failure |

The runtime preserves structured host-side diagnostics for admission, policy, allocation, and Core failures rather than forcing every condition into a capability-defined integer. The primitive status remains the portable result at the native boundary.

The query uses the same small status set: success, invalid argument, unsupported shape, and the range-related statuses where applicable. This fixture does not need a separate overflow status because its fixed requirement cannot overflow; a future variable-size capability must define an explicit overflow status in its own contract rather than reuse a semantic shape error.

## 9. Output and failure atomicity

For non-streaming workspace consumers such as argsort, the semantic contract requires:

```text
preflight/query failure → no workspace execution, no output
budget/allocation failure → no output
contract/range failure → no output
algorithm failure before emission → no output
```

`math.argsort.u32` must sort and construct its complete canonical result before its first callback. Therefore a failed query, denied allocation, primitive failure, or cancellation observed before output produces no result bytes.

Callback failure is different: once output has been synchronously committed to the host, the callback may have accepted a prefix. The runtime must report failure and must not claim an atomic result. The argsort primitive should emit only after all algorithmic failure points have passed, minimizing this case without adding a transactional output buffer.

## 10. Cancellation and cleanup

The callback, input, and workspace remain valid until the native call returns. A cancellation request while an in-process primitive is executing does not authorize the runtime to reclaim workspace or safely interrupt arbitrary native code.

The safe invariant is:

```text
cancellation requested
→ native call eventually returns or an external isolation mechanism ends it
→ runtime reclaims workspace
```

If a future isolated worker is terminated, worker teardown owns memory reclamation; that is an isolation design, not a workspace ABI guarantee.

The runtime must reclaim the range on every post-reservation path: success, primitive failure, callback failure, cancellation after return, exception/error translation, and timeout handling after control returns. Cleanup must be structured so that loading, query, allocation, execution, and callback failures cannot bypass it.

## 11. Purity and security

Workspace is a resource declaration, not an effect declaration:

```text
math.argsort.u32
  effects: none
  deterministic: true
  workspace: required
```

The query and execution functions for a pure capability must have no external effects. CPU time, temporary memory, and output bandwidth remain runtime-governed resources.

The host-owned range is not a sandbox. A malicious in-process `.so` can read or write outside the supplied range, retain pointers, invoke undeclared symbols, or corrupt the host. Artifact hashing, ELF admission, workspace limits, and callback conventions do not establish isolation. Untrusted native execution still requires an isolated worker or appropriate sandbox.

## 12. C, Rust, and target portability

C sees only:

```c
uint8_t *workspace, size_t workspace_size
```

and must perform checked bounds and alignment operations before forming internal typed views. No hidden `malloc`, global mutable scratch, or `free` is permitted.

Rust exports `extern "C"` functions and receives `*mut u8` plus `usize`. It may form a temporary checked `&mut [u8]` only inside the call after validating nullability, length, and alignment. No Rust slice, allocator object, panic, or unwind crosses the boundary. A panic must be prevented or translated without unwinding through C.

The contract is valid on the already qualified targets:

```text
x86_64-linux-gnu: pointer 8 bytes, size_t 8 bytes
AArch64 GNU Linux: pointer 8 bytes, size_t 8 bytes
```

The `size_t` fields describe addressable spans in the executing process; they do not redefine fixed-width vBuf counts or persistent encoding. The 8-byte minimum is not x86-specific. No native AArch64 implementation is added by this specification.

## 13. Discovery, admission, and multi-capability artifacts

The semantic capability record must declare its execution contract before invocation. Schema v1 is not changed by this document. The frozen **proposed binding shape** for a future schema revision or explicitly versioned manifest extension is capability-level and pairs query/run in one object:

```json
"execution": {
  "family": "workspace",
  "version": 65536,
  "query": "bloom_primitive_workspace_required",
  "run": "bloom_primitive_run_vbuf_workspace"
}
```

The values are bindings to expected exports, not capability discovery. `family`, `version`, `query`, and `run` are all required for a workspace binding; a workspace-free binding remains `base-v1` and has no query or workspace run. The runtime must reject a missing, mismatched, or independently substituted query/run binding. This representation is frozen for the compatibility fixtures but is not live catalog schema: schema v1 and its production parser remain unchanged.

The requirement is primarily capability-level because one physical artifact may provide both workspace-free and workspace-requiring capabilities. The artifact-level admission result must nevertheless verify the exports needed by every admitted capability binding, and native policy applies to the whole physical artifact.

Registry discovery remains authoritative. The loader must never discover capabilities by inspecting arbitrary exports. It should load only an artifact already resolved for a capability, verify its declared execution family and required exports, then select the bound function.

A future descriptor can represent:

```text
artifact descriptor
→ capability binding
→ run function
→ optional workspace query function
```

The proposed neutral export names do not prevent this evolution, but exact symbol discovery, collision handling, descriptor layout, and function-pointer lifetime are deferred. A short-term one-capability artifact may use the direct exports without defining a permanent one-capability packaging rule.

## 14. Required implementation test matrix

The compatibility fixtures are test-only and are not production capabilities. They run through the production x86_64 runtime path and through the existing executable AArch64 ABI lane.

### Base compatibility

- existing ABI-v1 C artifact loads and runs unchanged;
- existing ABI-v1 Rust artifact loads and runs unchanged;
- workspace-free capabilities do not invoke query, allocation, or workspace exports;
- a workspace artifact missing a required workspace export is rejected before execution;
- base and workspace version mismatches are rejected deterministically;
- private/runtime symbols are not required.

### Query

- valid input returns deterministic size and alignment;
- repeated identical input returns identical requirements;
- valid empty input returns zero size and alignment 8;
- wrong capability shape fails without output or allocation;
- fixed-width count conversion overflow fails;
- `n × 16` overflow fails;
- invalid result alignment is rejected;
- query does not modify input, allocate, emit, or invoke effects.

### Runtime policy and execution

- requirement below the limit is allowed;
- requirement equal to the limit is allowed;
- requirement above the limit is rejected before execution;
- host allocation failure prevents execution;
- exact-size, correctly aligned workspace succeeds;
- one byte too small fails before algorithm output;
- null/zero and null/nonzero workspace combinations follow the specified rules;
- honest C and Rust fixtures write only within the supplied range;
- primitive cannot rely on workspace contents being initialized.

### Failure and lifetime

- query failure causes no execution;
- execution failure reclaims workspace;
- callback failure reclaims workspace and reports that output may be partial;
- no algorithmic output is emitted before argsort completion;
- cleanup occurs on every exit path;
- fixture behavior after return does not require or retain input, workspace, callback, or callback context.

### Portability and consumer

- C and Rust fixtures pass the same byte-level contract;
- x86_64 and AArch64 report pointer/`size_t` widths and alignment consistently;
- the AArch64 lane performs real callback execution and admission checks;
- only after these tests pass, `math.argsort.u32` is implemented and tested for stable canonical u64 permutations.

## 15. Compatibility and implementation boundary

### Frozen fixture results

The test-only fixtures are:

```text
tests/fixtures/workspace_abi.h
tests/fixtures/workspace_identity.c
tests/fixtures/rust_workspace/src/lib.rs
tests/aarch64/workspace_runner.c
```

The C and Rust fixtures both pass the frozen query/run contract on x86_64 Linux and the existing AArch64 QEMU lane. They use no hidden heap allocation or release function. They pass exact-size, oversized, undersized, misaligned, callback-failure, query-determinism, invalid-shape, and zero-range checks. Negative C fixtures cover a missing query export and a mismatched workspace version; failures are detected by test-only symbol/version inspection. The normal workspace-free ABI-v1 fixtures continue to pass unchanged.

ABI v1 is a hard compatibility constraint:

```text
BLOOM_PRIMITIVE_ABI_VERSION remains 0x00010000
bloom_primitive_abi_version remains unchanged
bloom_primitive_run_vbuf remains unchanged
```

Existing artifacts need not be rebuilt and are not forced through the workspace contract. This specification introduces no ABI-v1 change, no descriptor table, no new production semantic capability, and no `math.argsort.u32` implementation. The workspace loader/runtime integration is intentionally limited to explicitly bound capabilities and temporary test catalogs.

### Narrowest next implementation step

After architecture review, implement production support only if the contract is accepted: add the separately versioned family to the loader/runtime and the frozen capability binding representation, then run the matrix above on x86_64 and the existing AArch64 lane. `math.argsort.u32` remains the first consumer, but must be implemented in a later step.
