# `math.argsort.u32`

## Status

Implemented and registered as `math.argsort.u32@1.0.0` for the supported native Linux target. It is a pure, deterministic, non-streaming workspace capability.

## Contract

- **Input:** one canonical vBuf v0.6 standalone unsigned-u32 fixed-width array block.
- **Output:** one canonical vBuf v0.6 standalone unsigned-u64 fixed-width array block at `KeyID=0`.
- **Meaning:** output position `j` contains the original zero-based input index of the value at sorted position `j`.
- **Ordering:** unsigned-u32 ascending.
- **Stability:** equal values retain ascending original indices.
- **Empty:** canonical empty u32 array produces canonical empty u64 array.
- **Effects:** none.
- **Determinism:** identical canonical input produces identical canonical output.
- **Streaming:** false; output begins only after the complete permutation is computed.
- **Complexity:** `O(n log n)` time and `O(n)` declared workspace.

For `[24, 7, 42, 7]`, the result is `[1, 3, 0, 2]`.

## Workspace

The production workspace execution binding is:

```json
{
  "family": "workspace",
  "version": 65536,
  "query": "bloom_primitive_workspace_required",
  "run": "bloom_primitive_run_vbuf_workspace"
}
```

The query returns:

```text
required_size = 16 × count
required_alignment = 8
```

with checked arithmetic. The workspace is partitioned as:

```text
[ count × u64 permutation ][ count × u64 merge scratch ]
```

The input payload is borrowed directly and is not copied into workspace. The implementation performs little-endian byte loads and stores and does not rely on host endianness or packed native structs.

All count-proportional mutable algorithm storage is supplied by the host workspace. There is no hidden `malloc`, `free`, `calloc`, `realloc`, `alloca`, `mmap`, `brk`, global scratch, thread-local scratch, Rust `Vec`, or Rust `Box`.

## Output construction

After sorting, the permutation remains in the first workspace range. A fixed 256-byte local chunk buffer serializes payload chunks synchronously through the existing callback. The canonical vBuf header is a fixed 32-byte inline-count header for counts up to 65535 and a fixed 40-byte extended-count header otherwise. No count-proportional output buffer is allocated.

For empty input, the query reports zero workspace and alignment 8. The runtime passes `NULL, 0`; the primitive emits the canonical empty u64 array.

## Failure behavior

The query rejects malformed capability shapes, including wrong physical representation, wrong bit width, multiple-block/invalid geometry, and checked count/workspace overflow. The runtime performs authoritative Core validation before invoking the query.

The primitive defensively checks:

- non-null callback;
- input and workspace nullability;
- sufficient workspace size;
- 8-byte workspace alignment;
- checked workspace partition arithmetic.

Argsort emits no bytes until sorting succeeds. Query, budget, allocation, contract, and algorithm failures therefore produce no semantic output. A callback failure after accepted bytes follows the runtime's existing non-transactional synchronous output behavior.

Workspace budget is configured with:

```bash
--max-workspace-bytes N
```

or `BLOOM_MAX_WORKSPACE_BYTES`. Workspace execution is disabled when no limit is configured. The limit must be at least `16 × count`; equality is allowed.

## Artifact and portability

The artifact is admitted through the existing pure-native Linux checks: SHA-256 identity, target, ELF64 little-endian `ET_DYN`, machine, workspace exports/version, no forbidden dependencies, no initializers, and no unresolved imports. It does not require ABI-v1 exports because workspace execution is a separate execution family.

The primitive is implemented in C to match the existing pure native math artifacts and avoid adding a second production implementation language. Its public boundary is the frozen C-compatible workspace ABI. AArch64 cross-build/execution remains a separate ABI qualification lane; the production CLI path is currently validated on native x86_64 Linux.

## Composition and limitations

The result is a permutation, not sorted values. Hosts may use it to reorder domain objects while keeping domain identity outside the primitive. No domain schemas, field names, JSON, or application policy enter the artifact.

`math.sort.u32`, `math.lower_bound.u32`, and generic gather remain unimplemented. A direct `math.sort.u32` is not yet justified: once a generic gather primitive exists, `argsort.u32` plus gather can compose sorted values, while a direct sort would need evidence of a meaningful locality or materialization advantage. The simplest future `lower_bound.u32` contract is a physically sorted contiguous u32 array plus one target value returning a position. Its selected two-block vBuf framing is qualified in [`math-lower-bound-u32-qualification.md`](math-lower-bound-u32-qualification.md), but the capability remains unimplemented.
