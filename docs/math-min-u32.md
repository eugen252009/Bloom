# `math.min.u32` capability

## Qualification

The registry previously contained only `bytes.identity`; no reduction primitive overlapped this capability. Identity cannot be composed or coherently generalized into minimum reduction. `math.min.u32` is therefore the smallest orthogonal capability gap that adds useful computation without introducing overflow, ordering, NaN, comparator, or index-preservation policy.

The capability is domain-blind. Applications project values such as prices or ages into its primitive input contract and map the scalar result themselves; no domain object or schema crosses the primitive ABI.

## Contract 1.0.0

- **Input:** one known-size canonical vBuf v0.6 stream containing exactly one standalone unsigned `u32` array block.
- **Output:** one known-size canonical vBuf v0.6 stream containing exactly one unsigned `u32` scalar block.
- **KeyID:** any generic input KeyID is accepted and preserved on output.
- **Empty array:** error; primitive status `2`, with no output.
- **Wrong representation:** error; primitive status `3`, with no output.
- **Effects:** none.
- **Deterministic:** yes; equal canonical input bytes produce equal canonical output bytes.
- **Streaming:** input and output are not streaming under ABI v1; output starts only after the complete input has been validated and scanned.
- **Materialization:** the current runtime materializes the complete serialized input. The algorithm itself uses `O(1)` auxiliary state.
- **Complexity:** `O(n)` time and `O(1)` auxiliary algorithm state.
- **Overflow:** not applicable; values are compared, not arithmetically accumulated.

## Existing vBuf Core representation

No Bloom wire format was added. The contract reuses normative vBuf v0.6 fields:

```text
Semantic   = 0 (unsigned integer)
BitWidth   = 32
Physical   = 1 (fixed-width array) for input
Physical   = 0 (scalar) and Count = 1 for output
byte order = little-endian
```

Array count comes from canonical `InlineCount` or `ExtendedCount`. Payload placement is derived by Core's checked formulas from `BaseShift`, `PayloadShift`, and block-header size. The contiguous payload length is exactly `Count × 4`; Core guarantees its complete bounded range and canonical alignment before ABI invocation. Scalar output uses the same primitive representation with count one. KeyID remains a generic identifier and gains no domain meaning.

The runtime first validates the complete stream through authoritative vBuf Core. The primitive then defensively checks its narrower single-block representation contract. It reads little-endian values directly from the borrowed ABI input payload without creating a C array or per-element ABI calls. This is zero-copy within the primitive, not end-to-end: the current CLI/runtime still reads stdin into memory, spools it for the path-based Core validator, and copies it into ABI storage. Byte-wise loads avoid assuming native pointer alignment or host-endian object layout.

The output is a fixed 36-byte canonical v0.6 scalar stream assembled on the primitive stack and emitted once through the ABI callback. The authoritative fixture writer and Core reader validate those bytes in tests.

## Use

```bash
cat build/fixtures/math.min.u32/normal-input.vbuf \
  | ./build/bloom run math.min.u32 \
  > result.vbuf
cmp build/fixtures/math.min.u32/normal-expected.vbuf result.vbuf
```

The source fixture contains `42, 7, 900, 23, 11`; the result scalar is `7`.

## Qualification for indexed algorithms

`math.argmin.u32` now implements the first index-returning reduction described below. Argsort is now implemented through the workspace execution family and documented in [`math-argsort-u32.md`](math-argsort-u32.md). Sorting, binary search, and strided views remain unimplemented; their current qualification is in [`math-argmin-u32.md`](math-argmin-u32.md).

1. **Original identity:** preserve it as the element's zero-based position in the projected primitive sequence. Domain identity remains with the host.
2. **Sorting outputs:** prefer separate semantic capabilities: value sorting returns reordered primitive values, while argsort returns a permutation/index array. A combined result should be added only if measured composition costs justify it.
3. **Host mapping:** a host projects `products[i].price` in product order, receives an index `i`, and evaluates `products[i]`. Products never cross the primitive ABI.
4. **View metadata:** primitive type and count are required; contiguous fixed-width data has an implicit stride of `BitWidth / 8`. Arbitrary views may additionally need stride and field offset. Binary search also needs an explicit sortedness/order precondition.
5. **Already in Core:** semantic primitive type, bit width, scalar/array cardinality, count, payload range, byte order, canonical alignment, and checked subranges.
6. **Above Core:** domain field roles, field offsets into application records, arbitrary strided-view semantics, sortedness/order guarantees, permutation meaning, and not-found/index-result conventions belong in a primitive contract or a vBuf-Tool-style superset—not vBuf Core.
7. **Copy behavior:** indexed algorithms need not copy domain objects. A contiguous projected primitive array can be borrowed directly. Projection from object records may still require materializing primitive values until a qualified checked strided-view contract exists.

That index-returning qualification is now implemented as `math.argmin.u32`, with first-minimum and empty-input behavior defined by its contract.
