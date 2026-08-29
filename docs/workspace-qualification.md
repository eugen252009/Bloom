# Invocation-scoped workspace qualification

## Status

The workspace ABI is now runtime-integrated but has no production semantic capability. No `math.argsort.u32` artifact, allocator, or catalog schema-v2 change is implemented; workspace bindings are accepted only through the explicit compatible execution field.

The concrete requirement comes from `math.argsort.u32`: stable bottom-up mergesort over original indices needs an owned permutation and merge scratch while reading a borrowed u32 payload:

```text
permutation:   8n bytes
merge scratch: 8n bytes
fixed state:   O(1)
----------------------
total:        16n bytes
```

Here `n` is the validated input array count. The input values remain borrowed; domain objects never enter the native boundary. The output is a new canonical u64 permutation array. The capability remains pure: temporary memory and CPU are resources, not filesystem, network, process, clock, or randomness effects.

## Model comparison

### Model A: one pre-sized scratch range

The host derives a checked workspace bound, reserves one suitably aligned mutable byte range, and passes it for one invocation:

```text
validated input
    ↓
checked required size/alignment
    ↓
host-owned scratch range
    ↓
primitive partitions range internally
    ↓
primitive returns
    ↓
host reclaims range
```

The primitive can partition the range as:

```text
[ permutation: 8n ][ merge scratch: 8n ]
```

Advantages:

- smallest ABI surface: one pointer and one length plus existing call arguments;
- no allocator protocol or cross-language ownership object;
- deterministic accounting and no fragmentation;
- one cleanup action on every exit path;
- straightforward C/Rust/Zig use as raw pointer plus native span;
- sufficient for argsort and algorithms whose bound is known before execution.

Costs:

- the host must know a safe bound before execution;
- the primitive must use checked internal partitioning and explicit alignment;
- algorithms with genuinely data-dependent workspace may need a later model;
- a single invocation cannot return workspace to the host early.

This is the selected first model. It solves the demonstrated argsort requirement without introducing general-purpose allocation.

### Model B: invocation-scoped scratch arena

The host provides an arena context and a callback such as `alloc(size, alignment)`. The primitive may request multiple ranges; the host discards the entire arena at invocation end.

Advantages:

- supports several independent or data-dependent allocations;
- lets the primitive avoid manually partitioning one range;
- can support algorithms whose workspace phases are difficult to precompute.

Costs:

- larger ABI surface and callback lifetime rules;
- more complicated C/Rust/Zig bindings and reentrancy behavior;
- fragmentation and allocation-order concerns;
- more failure points and harder resource accounting;
- an arena callback starts to resemble a general host-service table;
- it is unnecessary for argsort's fixed `16n` bound.

An arena remains an open future option for a concrete capability that proves Model A insufficient. It is not selected now.

## Is public `free()` necessary?

No. Public `free()` is not necessary for the selected invocation-scoped model, and it should not be added merely to resemble conventional heap APIs.

The host owns one range for exactly one invocation. The primitive may borrow and partition it but must not retain it, transfer it, or release it. The host reclaims the whole range after success, primitive failure, callback failure, cancellation after native control returns, timeout handling, or any other exit path.

A public `free()` would add double-free, invalid-free, use-after-release, allocator mismatch, and ownership ambiguity failure modes without improving the demonstrated algorithm. Early release can be considered only if a real capability proves peak-lifetime reduction materially matters; then it should be an explicitly scoped range protocol, not general `free(void *)`.

## Is a general allocator necessary?

No for the first demonstrated consumer. Argsort's bound is derived from validated geometry:

```text
required_bytes = checked_mul(count, 16)
required_alignment = alignof(uint64_t)
```

The bound is known before native execution. Other likely classes can be classified as follows:

| Class | Examples | First model |
|---|---|---|
| Bound known from validated geometry | argsort, many FFT/matrix plans, fixed index construction | pre-sized range |
| Bound known from contract/input limits | bounded parser tables, fixed compression windows | pre-sized range |
| Grows dynamically from data | graph frontier, irregular parse/index structures | qualify separately; do not assume arena |

This does not claim every future algorithm fits Model A. It means no current capability has demonstrated the need for a general allocator or multiple allocation events.

Rust `Vec`, C `malloc`, direct `mmap/brk`, static globals, thread-local arenas, and unbounded `alloca` are not substitutes. Implementation-language allocation is distinct from a Bloom workspace contract and would evade runtime limits.

## Workspace sizing and preflight

The first sizing mechanism should be explicit capability metadata, not a programmable manifest expression language. For argsort, the contract can state the formula:

```text
count = validated input u32-array count
required_bytes = checked count × 16
required_alignment = 8
```

The runtime already performs authoritative vBuf validation and has the count available through its validated view. It should perform the capability-specific checked formula once, enforce the invocation memory budget, and reserve the range before the primitive starts. The primitive repeats only the narrow safety checks needed for its own partitioning; it must not duplicate a complete vBuf parser.

A future manifest representation may carry structured resource metadata such as:

```text
resources.workspace:
  kind: exact-bound
  bytes_per_input_element: 16
  alignment: 8
```

or a named contract rule understood by the runtime. Do not accept arbitrary executable expressions from manifests. Until workspace-capable invocation exists, no schema field is added.

Preflight is preferable to a host guess. A guessed maximum either over-allocates or creates avoidable insufficient-workspace failures. The reviewed specification selects a pure query export for the first general implementation because the current runtime has no generic validated count view and must not embed argsort semantics. The query only derives the capability-specific requirement; it does not execute the algorithm or duplicate Core validation. The runtime must reject overflow or over-budget requests before native execution. See [`workspace-abi-spec.md`](workspace-abi-spec.md) for the proposed calling and query contract.

## Proposed future calling boundary

Do not mutate the meaning of ABI v1's existing two-symbol call. Existing borrow-only artifacts must continue to load unchanged. The first workspace-capable artifact should use the separately versioned workspace execution family frozen for compatibility testing in [`workspace-abi-spec.md`](workspace-abi-spec.md), selected by capability metadata before execution. This is an orthogonal feature, not a replacement for ABI v1. Runtime/catalog integration remains unimplemented.

The minimal semantic parameters are:

```text
const uint8_t *input
size_t input_size
uint8_t *scratch
size_t scratch_size
bloom_primitive_write_fn write
void *write_context
```

The scratch pointer is host-owned mutable storage, valid only for the call. `scratch_size` uses the same target-native span convention as ABI v1; persistent vBuf counts remain fixed-width and are checked before conversion. The ABI must document that no pointer, including scratch, may escape the invocation.

A flat descriptor is not needed for this first model. If later negotiation requires one, it must use explicit size/version fields, fixed-width flags, pointer-plus-length pairs, reserved fields, and documented alignment/lifetime rules. No allocator table or general host-service table is justified.

## Alignment

The host must provide the selected range aligned to at least 8 bytes, sufficient for u64 index storage on the currently qualified x86_64 Linux and AArch64 Linux GNU targets. The contract should express this as an explicit power-of-two minimum (`8`), not as undocumented allocator behavior or a serialized property.

The primitive may partition the range only at checked offsets preserving that alignment. If a future algorithm requires a larger alignment, preflight must report it and the host must satisfy or reject it. Invalid alignment is a deterministic pre-execution failure.

Portable raw-byte partitioning remains the ABI boundary. C/Rust implementations may form appropriately aligned internal views only after checking pointer, length, and alignment; language-native slices do not cross the ABI.

## Resource limits and failure semantics

Workspace is an invocation resource. For argsort:

```text
if count × 16 overflows: reject before execution
if required_bytes > invocation_workspace_limit: reject before execution
if supplied scratch_size < required_bytes: reject before execution
if scratch address is not aligned: reject before execution
```

The exact error-code allocation is deferred with the future ABI version, but all failures must be explicit and deterministic. `math.argsort.u32` emits no output before sorting and output construction completes, so workspace denial, allocation failure, primitive failure, cancellation, and callback failure produce no partial semantic output.

The selected contract must also reject impossible pointer/size conversions and any internal range partition overflow. It must not use wrapping arithmetic.

## Cleanup and cancellation

The runtime owns cleanup. It must discard the one range on:

```text
success
workspace denial
primitive failure
output callback failure
validation/admission failure after reservation
cancellation
native timeout handling after control returns
```

A synchronous native call cannot be safely forcibly interrupted by this contract. Logical cancellation may be recorded while native code runs, but workspace cannot be reclaimed until control has returned, unless a future isolated worker supplies a separate process-termination boundary. This does not claim sandboxing or forced native termination.

The primitive must not participate in cleanup and must not retain a pointer after return. The host must not reuse or release the range while the call is active.

## Cross-language and cross-architecture requirements

Model A is expressible identically in C, Rust, and Zig as raw pointer plus native size:

```text
C:    uint8_t * + size_t
Rust: *mut u8 + usize, checked temporary slice internally
Zig:  [*]u8 + usize, checked temporary slice internally
```

No language-native allocation or exception crosses the boundary. Rust must use `extern "C"` and abort or contain panics; C++ exceptions and other unwinds must not cross.

The already-qualified targets are compatible with the model:

```text
x86_64-linux-gnu  pointer=8, size_t=8
AArch64 GNU Linux pointer=8, size_t=8 (QEMU ABI execution)
```

Both need tests for exact-boundary success, over-budget denial, checked multiplication overflow, invalid alignment, insufficient range, callback failure, primitive failure, cleanup, and no output before failure. The existing ABI-v1 C/Rust artifacts must continue to pass unchanged on both target lanes. The exact workspace fixture matrix is specified in [`workspace-abi-spec.md`](workspace-abi-spec.md); no workspace fixture is added during this specification-only task.

## Effects versus resources

Keep these declarations independent:

```text
math.argsort.u32
  effects:   none
  resources: CPU + workspace memory + output bandwidth
```

Resource limits are runtime policy and capability metadata. They do not become vBuf fields, native effect imports, or permission grants. Temporary memory does not make a pure algorithm effectful.

## Qualification result

- **Selected model:** one pre-sized host-owned scratch range.
- **Arena:** deferred; no current demonstrated need.
- **Public `free()`:** rejected as unnecessary.
- **General allocator:** rejected for this step.
- **ABI v1:** unchanged; borrow-only artifacts remain compatible.
- **Workspace specification:** frozen, compatibility-tested, and integrated into the production loader/runtime path for explicitly bound capabilities; no production semantic capability is registered.
- **Argsort:** still blocked until that workspace calling surface is compatibility-tested.

## Narrowest next step

After architecture review, implement only the production loader/runtime integration for the frozen workspace family and reviewed capability binding. Then implement `math.argsort.u32` as its first consumer.
