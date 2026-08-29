# `math.lower_bound.u32` qualification

## Status

**Qualified but not implemented or registered.** The input representation is expressible with existing canonical vBuf v0.6 blocks, so no new ABI, workspace model, argument-list format, or Core representation is required. This document deliberately does not implement the capability.

## Existing vBuf mechanisms inspected

The authoritative vBuf v0.6 Core provides:

- one canonical root containing an ordered sequence of physical blocks;
- generic 16-bit local `KeyID` values;
- unsigned fixed-width scalar and array representations;
- canonical inline or extended counts;
- checked payload and inter-block ranges/alignment;
- legal duplicate KeyIDs and explicit continuation chains;
- borrowed typed/payload views after complete validation.

The current C API exposes validated block lookup by `(KeyID, occurrence)` and typed views. The current Bloom runtime passes one serialized vBuf byte span to a primitive after Core validation.

The v0.6 structures inspected here do not define a special typed nested-root value or a generic argument-list object. README-level nested-root direction does not add a current v0.6 argument ABI. A future nested-root/profile design may exist, but it is not needed for this fixed-arity capability and must not be inferred as implemented behavior.

## Candidate representations

### A. Two blocks in one root — selected

```text
one canonical vBuf root
├── KeyID 1: unsigned-u32 fixed-width array (sorted values)
└── KeyID 2: unsigned-u32 scalar (target)
```

This reuses Core directly, has minimal structural overhead, is easy for C/Rust primitives to locate, and composes naturally with other primitives producing standalone vBuf values. Role meaning remains in the capability contract; Core continues to treat KeyID as a generic local identifier.

The contract requires exactly one block for each role, in that order, with no continuation. This avoids duplicate-occurrence ambiguity while retaining Core's general duplicate-KeyID rules for other uses.

### B. Nested roots — deferred, not selected

Nested roots could provide strong composition and local namespaces if a vBuf profile explicitly defined typed child-root blocks and range-backed composition. The currently inspected v0.6 Core block model does not provide a dedicated nested-root typed view in the Bloom boundary. Even if it did, two nested child roots add headers and require a higher-level child-role contract without helping this fixed pair.

Nesting remains useful for independently reusable structured values and future compositions, but it is not justified for the first lower-bound contract.

### C. Positional blocks — rejected as the semantic rule

Treating physical block 0 as values and block 1 as target would make meaning depend on physical ordering alone. It is fragile under generic block composition, continuation, and future extension. Physical order can remain canonical serialization order, but local role KeyIDs should identify the two contract inputs.

### D. Dedicated higher-level argument contract — deferred

A vBuf-Tool or Bloom superset may eventually describe named roles, preconditions, or reusable multi-input envelopes. It is not required here. A generic `Variant[]`, argument descriptor array, named map, JSON object, or reflection layer would add ambiguity and runtime surface without solving a demonstrated structural gap.

## Selected representation

The future capability input is one standalone canonical root containing exactly two physical blocks:

```text
block 0:
  KeyID      = 1 (local role: sorted values)
  Semantic   = unsigned integer
  BitWidth   = 32
  Physical   = fixed-width array
  Count      = n, including zero
  Continuation = 0

block 1:
  KeyID      = 2 (local role: target)
  Semantic   = unsigned integer
  BitWidth   = 32
  Physical   = scalar
  Count      = 1
  Continuation = 0
```

The root must contain no other physical blocks. In particular, the primitive rejects:

- missing KeyID 1 or KeyID 2;
- more than one block for either role;
- any continuation flag;
- any extra block, including an unrelated KeyID;
- wrong semantic type, bit width, or physical cardinality;
- malformed or non-canonical block geometry.

KeyID 1 and KeyID 2 are **local role identifiers of this capability contract**, not global Bloom assignments. Core remains unaware that 1 means values or 2 means target. A capability contract may use different local role IDs in a different fixed contract, but there is no global registry of algorithm argument IDs.

The values block precedes the target block in canonical contract serialization. Role identity comes from the KeyID; the required order makes the fixed input deterministic and prevents otherwise-valid role permutations from creating multiple encodings for one logical input.

## Canonical serialization

The selected input is ordinary canonical vBuf v0.6 serialization:

```text
vBuf header
→ canonical KeyID-1 u32 array block
→ zero canonical inter-block padding if required
→ canonical KeyID-2 u32 scalar block
```

The array count uses the Core-selected inline or extended form. The scalar count is exactly one. Each payload uses Core's checked alignment rules and little-endian encoding. No workspace pointer, argument descriptor, allocator identity, sortedness flag, or role map is serialized into vBuf.

The native ABI remains one serialized input span:

```c
bloom_primitive_run_vbuf(... input, input_size, ...)
```

No `run(input1, input2, ...)` signature is introduced.

## Exact future capability contract

```text
Name:          math.lower_bound.u32

Input:         one canonical vBuf v0.6 root with exactly:
               KeyID 1 = unsigned-u32 fixed-width array
               KeyID 2 = unsigned-u32 scalar

Values:        KeyID 1 array, required to be sorted ascending under
               unsigned-u32 numeric order
Target:        KeyID 2 scalar

Output:        one canonical vBuf v0.6 unsigned-u64 scalar at KeyID 0

Meaning:       the least position i such that values[i] >= target
               where 0 <= i <= count

No match:      count
Duplicates:    first equal position
Empty:         empty values array returns 0
Deterministic: yes
Effects:       none
Time:          O(log n) comparisons
Workspace:     O(1); no workspace execution family required
Streaming:     non-streaming one-shot input/output in the current runtime
```

Examples:

```text
values [1, 4, 4, 9, 15], target 4  → 1
values [1, 4, 4, 9, 15], target 10 → 4
values [1, 4, 4, 9, 15], target 20 → 5
values [], target 4                  → 0
```

The result is an insertion position, not an original element identity. `count` is therefore a valid u64 result even though it is not an index of an existing element. This differs from `math.argmin.u32`, whose result identifies an existing input position.

## Core versus capability semantics

Core owns:

```text
block order
KeyID syntax
unsigned/u32 and scalar/array representation
counts
canonical geometry
alignment
checked ranges
nested/opaque structural rules when defined by Core
```

The capability owns:

```text
KeyID 1 role = sorted values
KeyID 2 role = target
exact two-block arity
ascending sortedness precondition
lower-bound meaning
u64 insertion-position result at KeyID 0
```

Neither “sorted”, “target”, “haystack”, nor “lower bound” should be added to vBuf Core for this capability. They are semantic contract roles, not generic structural mechanics.

## Sortedness precondition

The primitive must not sort its input. Sorted ascending unsigned-u32 order is a semantic precondition.

The first lower-bound contract should **not** scan the complete array to validate sortedness: doing so changes the intended O(log n) operation into O(n) validation and duplicates a separate reusable validation capability. The caller or an earlier pipeline stage is responsible for establishing the precondition. If the precondition is violated, the input is outside the contract; the implementation may return a capability-contract error if it defensively detects a local violation, but it must not promise a correct lower bound for unsorted input.

Current catalog metadata has no precondition field. No schema change is made. A future declarative precondition field may state a reviewed named condition such as `sorted_ascending_unsigned_u32`, but it must not become an executable predicate language. A separate `math.is_sorted.u32` capability could validate the condition in O(n) if a concrete pipeline needs runtime checking; it is not proposed or implemented here.

## Native parsing burden

The future primitive performs only narrow parsing after host-side Core validation:

1. locate KeyID 1 occurrence 0 and KeyID 2 occurrence 0;
2. ensure there are exactly two physical blocks and no continuation;
3. check unsigned-u32 array/scalar representations and counts;
4. obtain the borrowed u32 array payload and scalar value;
5. perform binary search using checked count/index conversions;
6. emit one canonical u64 scalar.

It does not implement a replacement Core parser or generic argument decoder. A Core validated view API could reduce repeated byte inspection in the future, but no such API is required to qualify this representation.

## Multi-input generality without a universal argument ABI

The selected pattern generalizes mechanically to other small fixed contracts:

```text
KeyID A = vector, KeyID B = permutation
KeyID A = matrix, KeyID B = index vector
KeyID A = values, KeyID B = threshold
```

Each capability explicitly defines roles, types, arity, continuation policy, and extra-input policy. The pattern does not define one universal dynamic argument object. Dynamic optional arguments, maps, variants, and reflection remain outside the native boundary.

## Direct versus indirect search

### Direct contiguous lower bound — recommended first

```text
sorted contiguous u32 values + u32 target → position
```

This has the simplest two-input contract, direct payload access, predictable O(log n) comparisons, and no workspace. It is the selected future contract.

### Indirect permutation search — deferred

```text
original u32 values + u64 permutation + target → position or original index
```

This avoids materializing sorted values but adds a third input, an indirection on every comparison, and ambiguity about whether the result is a sorted position or original identity. It should not precede evidence that materializing sorted values is a real cost.

## Relationship to argsort and gather

`math.argsort.u32` produces a u64 permutation but not sorted values. A future generic gather capability could compose:

```text
values
→ argsort
→ permutation P
→ gather(values, P)
→ sorted u32 values
→ lower_bound(values, target)
```

This preserves domain blindness and keeps lower-bound's contract contiguous. The current runtime has no generic gather, so this is a future composition, not an implementation claim. Direct indirect search is not justified merely because argsort already exists.

## Zero-/low-copy qualification

The selected structure can be assembled from two existing standalone logical values without changing their semantics, and its roles are independently addressable by local KeyID. That is the structural low-copy property.

The current Bloom runtime, however, reads stdin into one `bytes` object and the current Core validation seam validates through a temporary file. It has no range-backed/scatter-gather vBuf composition API. Therefore the current implementation may materialize a new serialized root; zero-copy composition is not claimed.

A future runtime may construct the same canonical root from borrowed ranges or nested roots without copying payloads, provided it preserves canonical block geometry and lifetime. That optimization must not cross the native ABI as an object graph or descriptor.

## Nested-root overhead and decision

A nested representation would require at least an outer block/range framing plus each child root's own header and local structure. It could preserve independently relocatable child roots, but the current fixed lower-bound contract does not need independent child namespaces: the two roles already have distinct local KeyIDs in one root. Ordinary blocks are therefore both clearer and smaller for this use.

## Qualification tests

No production capability or tests are added because lower-bound is not implemented. The first implementation should add structural fixtures for:

- valid two-block input;
- missing values or target;
- duplicate role blocks;
- extra unrelated block;
- continuation flag;
- wrong u16/u64/signed/opaque representation;
- target scalar encoded as an array;
- empty values array;
- malformed Core input and malformed child/root framing if nesting is later supported.

Each successful fixture must validate through authoritative Core. Contract-invalid but Core-valid inputs must fail in the capability layer, demonstrating the boundary between structural and semantic validation.

## Current decision

- **Selected:** two ordinary blocks in one canonical root, local KeyID 1/2 roles, exact two-block arity.
- **Core changes:** none.
- **Higher-level argument container:** none.
- **Nested roots:** deferred, not needed.
- **Positional-only semantics:** rejected.
- **Direct contiguous search:** recommended first.
- **Indirect permutation search:** deferred.
- **Workspace ABI:** unchanged; lower bound needs O(1) state.
- **Implementation:** not ready for production implementation in this task only because the capability itself remains intentionally deferred; no representation blocker remains.

The narrowest next step is to review this fixed-arity representation, then implement `math.lower_bound.u32` as a separate O(log n), O(1)-workspace capability with authoritative two-block fixtures. Do not introduce a generic argument ABI.
