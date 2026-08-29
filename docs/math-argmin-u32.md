# `math.argmin.u32` capability

## Qualification

`math.min.u32` returns a value and cannot be composed into the original position once duplicate values exist. Generalizing it to sometimes return a value and sometimes an index would make its output contract incoherent. `math.argmin.u32` is therefore an orthogonal indexed reduction: it proves stable host identity mapping while remaining domain-blind.

A host preserves order while projecting domain values, invokes this primitive, and interprets the returned position against that same host sequence. Domain objects and their identifiers never cross the Bloom ABI.

## Contract 1.0.0

- **Input:** one known-size canonical vBuf v0.6 stream containing exactly one standalone unsigned `u32` array block.
- **Output:** one known-size canonical vBuf v0.6 stream containing exactly one unsigned `u64` scalar block at `KeyID=0`.
- **Result:** the zero-based position of the minimum value in the exact input sequence.
- **Ties:** first minimum; the lowest position whose value equals the minimum is returned.
- **Input KeyID:** any generic KeyID is accepted and does not alter the result.
- **Empty array:** error; primitive status `2`, with no output.
- **Wrong representation:** error; primitive status `3`, with no output.
- **Effects:** none.
- **Deterministic:** yes; equal canonical input bytes produce equal canonical output bytes.
- **Streaming:** input and output are not streaming under ABI v1; output starts only after the complete input has been validated and scanned.
- **Materialization:** the current runtime materializes the complete serialized input. The algorithm itself uses `O(1)` auxiliary state.
- **Complexity:** `O(n)` time and `O(1)` auxiliary algorithm state.
- **Overflow:** no arithmetic accumulation occurs; the result width covers every representable zero-based vBuf count position.

The implementation updates its best position only for a strict smaller-than comparison. Equal later values therefore cannot replace the first minimum.

## Existing vBuf Core representation and result width

Input reuses the representation already qualified by `math.min.u32`:

```text
Semantic   = 0 (unsigned integer)
BitWidth   = 32
Physical   = 1 (fixed-width array)
byte order = little-endian
```

vBuf v0.6 count is a canonical `u64`, encoded as `InlineCount` or `ExtendedCount`. Core also requires checked `u64` computation of `payload_bits = count × 32`, so the wire-level maximum valid u32-array count is at most `floor(UINT64_MAX / 32)`; file and host-size limits may reduce it further. That bound still exceeds `UINT32_MAX`. For every non-empty valid array, its zero-based positions fit in `u64`, while they do not necessarily fit in `u32`, so the result uses a `u64` scalar rather than matching the input element width.

The result uses the existing Core unsigned scalar representation:

```text
Semantic = 0 (unsigned integer)
BitWidth = 64
Physical = 0 (scalar)
Count    = 1
KeyID    = 0 (defined by this capability contract)
```

No Core type or Bloom-specific index encoding was added.

## KeyID decision

vBuf Core defines KeyID only as a generic numeric identifier; it defines neither a neutral value nor application meaning. Copying the input key would imply that an index scalar has the same role as the input value sequence. Instead, contract 1.0.0 explicitly places its sole result at `KeyID=0`. This is a capability-level framing decision, not domain semantics or a new Core rule. Consumers identify the semantic result through the capability contract, not through a globally meaningful KeyID.

## Native data path

The runtime validates the complete stream through authoritative vBuf Core. The primitive defensively checks its narrower one-block representation, derives the canonical payload range, and reads little-endian values directly from the borrowed ABI bytes. It creates no temporary value or index array and performs no per-element host call. The result is a fixed 40-byte canonical v0.6 stream assembled on the stack and emitted in one callback.

This is zero-copy with respect to the primitive's input payload, not end-to-end zero-copy. The current CLI/runtime still materializes stdin, validates through a temporary file, and copies bytes into ctypes ABI storage. Byte-wise reads avoid unaligned native casts and host-endian assumptions.

## Use

```bash
cat build/fixtures/math.argmin.u32/normal-input.vbuf \
  | ./build/bloom run math.argmin.u32 \
  > index.vbuf
cmp build/fixtures/math.argmin.u32/normal-expected.vbuf index.vbuf
```

The input contains `42, 7, 900, 23, 11`; the result is the `u64` scalar position `1`.

## Qualification for argsort and binary search

The argsort capability is now implemented; binary-search capabilities discussed below remain unimplemented.

### Argsort index representation

An argsort result can physically use an existing canonical unsigned `u64` array whose values are original zero-based positions. `u64` is required for the same reason as argmin: vBuf count is `u64`. The fact that the array is a permutation is a primitive contract guarantee above Core, not a new primitive representation. A complete argsort output has the same element count as its input and inherently emits `8 × count` payload bytes.

### Stable ordering

`math.argsort.u32` should be stable: equal keys retain ascending original position. This makes repeated output deterministic and preserves host order among equal projected values, so mapping indices back to domain objects does not arbitrarily reorder peers. Equivalently, original position can act as the deterministic tie-break after value comparison.

### Search preconditions

“Sorted ascending under unsigned-u32 ordering” is semantic, not structural. It belongs in a binary-search primitive precondition. If a reusable checked view later carries such a guarantee, vBuf-Tool/Bloom metadata may declare and validate it, but vBuf Core should continue to describe only canonical representation and ranges.

Exact binary search must also specify duplicate and not-found behavior. Orthogonal operations such as `lower_bound`, `upper_bound`, and exact-match search should not be conflated without a concrete contract.

### Search result and host identity

A binary search should return a position in its immediate sorted primitive input. It cannot independently know an original host index. A host can compose:

```text
projected values in host order
→ argsort permutation
→ sorted projected values
→ binary search position p
→ permutation[p]
→ original host object
```

Initially, the host may retain and apply the permutation. A specialized binary search returning original host indices would couple search to permutation policy and should not precede evidence that the orthogonal composition is insufficient.

### Data movement

Binary search can directly borrow a contiguous canonical primitive array and needs `O(1)` state. Argsort can compare input values in place without copying domain objects, but must allocate/order indices and serialize a new permutation array. Constructing sorted projected values from a permutation may require a primitive gather or host materialization; neither is implemented. A strided view becomes relevant only if repeated host projection/materialization is shown to be a real cost, so no strided contract is designed here.

The original argsort qualification is recorded in [`math-argsort-u32-qualification.md`](math-argsort-u32-qualification.md), and the implemented contract is documented in [`math-argsort-u32.md`](math-argsort-u32.md). The workspace execution family now supplies the explicit invocation-scoped allocation boundary; binary search and gather remain separate future capabilities.
