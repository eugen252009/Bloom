# `math.argsort.u32` qualification

## Status

**Workspace boundary integrated; capability not implemented or registered.**

The capability gap is real and orthogonal. `math.min.u32` returns a value and `math.argmin.u32` returns one position; neither can be composed into a complete stable permutation. Generalizing either reduction would make its contract incoherent. No existing capability provides sorting or permutation output.

## Qualified semantic contract

A future contract `1.0.0` should be:

- **Input:** one known-size canonical vBuf v0.6 stream containing exactly one standalone unsigned `u32` array block.
- **Output:** one known-size canonical vBuf v0.6 stream containing exactly one unsigned `u64` array block at `KeyID=0`.
- **Output count:** exactly the input count.
- **Meaning:** `output[j]` is the original zero-based input position of the value at ascending sorted position `j`.
- **Ordering:** unsigned-u32 numeric ascending.
- **Stability:** for equal values, lower original positions occur first.
- **Empty input:** valid; an empty u32 array produces a canonical empty u64 array.
- **Wrong representation:** capability error with no output.
- **Effects:** none.
- **Deterministic:** yes.
- **Streaming:** no; globally ordered output cannot start until ordering is established.
- **Complexity target:** `O(n log n)` time with explicit `O(n)` workspace.

For `[24, 7, 42, 7]`, the output is `[1, 3, 0, 2]`. Input values are borrowed and remain unchanged.

### Existing Core representations

No new Core representation is needed:

```text
input:  Semantic=Unsigned, BitWidth=32, Physical=Array
output: Semantic=Unsigned, BitWidth=64, Physical=Array
```

vBuf v0.6 permits array count zero, so `[] -> []` is canonical. Permutation meaning is a capability guarantee above Core, not a physical type.

The index width is `u64`, consistent with `math.argmin.u32`. Core count is `u64`; checked u32 payload arithmetic permits counts above `UINT32_MAX`, although file and host limits may lower the practical maximum. A u32 permutation could therefore truncate valid positions.

The output uses contract-defined `KeyID=0`. Copying the input values' KeyID would imply that a permutation contains the same semantic quantity. Core assigns no global meaning or neutral status to any KeyID; this is capability framing only.

## Why ABI v1 is insufficient

A practical stable argsort needs a mutable position array with one entry per input element. ABI v1 provides only:

```text
borrowed const input bytes
append-only synchronous write callback
```

It provides no output reservation, mutable output range, scratch range, allocator, or host import table. The callback copies committed bytes and cannot expose them for sorting or revision. The pure-artifact policy also rejects unresolved allocator imports and dynamic dependencies.

The following workarounds were rejected:

- **Count-sized VLA or `alloca`:** untrusted count controls stack consumption and can crash the host; a fixed cap would create an artificial non-general capability.
- **Static artifact buffer:** imposes a fixed global limit, is unsafe for concurrency/reentrancy, and is not realistic production storage.
- **Direct `mmap`/OS syscalls:** hides an undeclared effect, bypasses runtime resource policy, and couples the artifact to one execution environment.
- **`malloc`/`qsort`:** introduces forbidden imports/dependencies and still leaves allocation limits outside runtime control; `qsort` is not stable.
- **Repeated scans with no index storage:** selecting and emitting successive positions can use constant memory, but is `O(n²)` for distinct values and is an obviously pathological substitute for bulk argsort.
- **Writing output as workspace:** the ABI callback is append-only and synchronously consumes bytes; it supplies no mutable storage.

Consequently, ABI v1 does not support this realistic count-proportional workspace capability, while the separately versioned workspace execution family now supplies the qualified boundary. No argsort artifact, manifest entry, catalog entry, or performance claim is produced.

## Proposed algorithm once workspace exists

A straightforward deterministic implementation is stable bottom-up mergesort over indices:

```text
borrowed input u32 payload
owned permutation: n × u64
owned merge scratch: n × u64
```

Initialize `permutation[i] = i`. Compare indices by `input[index]`; take from the left run on equality. This directly establishes stability without copying input values.

Workspace is:

```text
permutation: 8n bytes
scratch:     8n bytes
fixed state: O(1)
total:       16n bytes plus allocator metadata
```

After sorting, the primitive can emit a canonical v0.6 u64-array header followed by little-endian permutation chunks. No full copy of input values or domain objects is required. More specialized in-place stable algorithms could reduce scratch but would add substantial implementation complexity before allocation policy is solved.

## Narrow allocation ABI qualification

The required lifetime is one primitive invocation. Scratch must not escape or be retained by the artifact. Allocation must use checked size/alignment arithmetic, be denyable by runtime resource limits, and report failure before output begins.

The workspace qualification now selects a single pre-sized host-owned scratch range for this concrete consumer; it does not select an allocator callback or arena. Argsort's checked bound is `16 × count` bytes with 8-byte alignment. The host reserves the range before execution, the primitive partitions it internally, and the host discards it after return. No public `free()` is needed because the entire range has invocation scope.

The workspace qualification is documented in [`workspace-qualification.md`](workspace-qualification.md), and the separately versioned calling surface is frozen for compatibility testing in [`workspace-abi-spec.md`](workspace-abi-spec.md). Together they cover resource-versus-effect classification, sizing, limits, overflow, alignment, cleanup, cancellation, query behavior, and compatibility testing.

ABI v1 must remain supported unchanged for existing bounded-workspace artifacts. Argsort remains unimplemented and is deferred to a separate algorithm/semantic implementation task now that its workspace boundary is available and compatibility-tested. This qualification does not select descriptor tables, bundling, streaming lifecycle, or a general allocator.

## Binary-search and lower-bound qualification

### Physically sorted values versus permutation indirection

Searching `value[P[mid]]` avoids copying values and preserves an immediate route to original identity, but it reads two arrays, has poorer cache locality, and requires a more complex two-input contract. Materializing `sorted_values[mid]` costs `O(n)` copying but gives contiguous access and a simpler reusable search contract. The initial search primitive should favor contiguous sorted values; indirect permutation search should wait for measured evidence that avoiding materialization outweighs its complexity.

The host can retain the permutation in either case:

```text
lower-bound position j
→ permutation[j]
→ original host index
→ host object
```

Bloom should expose primitive positions and permutations, leaving domain identity lookup in the host. A combined domain-aware search operation is not justified.

### `lower_bound` as the fundamental operation

`math.lower_bound.u32` is more fundamental than an underspecified binary search. It gives a deterministic insertion position, naturally selects the first equal value, and supports exact search by checking whether the returned position is in range and equal to the query. Query framing and multi-input representation still require qualification before implementation.

### Sortedness

“Ascending unsigned-u32 order” is a semantic precondition of the search capability. It is not Core structure. A future checked vBuf-Tool view may carry validated sortedness metadata when reuse justifies it, but Core should continue to define only representation, count, geometry, and checked ranges.

### Permutation as index structure

A canonical u64 permutation already provides the information required for indirect ordered traversal. No dedicated search-index physical representation is justified without measured navigation or storage benefits.

## Narrowest next step

Specify and compatibility-test only the invocation-scoped pre-sized workspace-range contract driven by this capability, including denial, cleanup, overflow, alignment, output-before-failure, and resource-limit tests. Do not implement argsort in this task. It is the first qualifying consumer for a later algorithm implementation task.
