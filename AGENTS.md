# AGENTS.md

## Purpose

Bloom is a greenfield, vBuf-based capability ecosystem. Its central goal is to turn repeated agent reasoning into small, tested, reusable software assets rather than regenerating complete programs for each task.

Read `README.md` before making architectural changes. It is currently the source of truth for the project vision. The repository contains only the first narrow native vertical slice; do not present the broader speculative design as established behavior. For implemented ABI and build behavior, also consult `docs/primitive-abi-v1.md` and `docs/development.md`.

## Core priorities

In order of importance:

1. Reuse an existing primitive.
2. Compose existing primitives into an execution plan.
3. Generalize an existing primitive when its contract can remain coherent.
4. Create the smallest missing general-purpose primitive only when necessary.
5. Keep application-specific policy out of reusable primitives.

Optimize for a small, orthogonal capability space—not for the number of tools.

## Architectural boundaries

Keep these concepts separate:

- **vBuf Core:** structural mechanics only (blocks, checked ranges, nesting, alignment, continuation, opaque payloads).
- **vBuf supersets:** vBuf Core plus additional semantic and/or conformance rules, such as tool contracts or ML structures. Supersets may overlap and independently reuse generic rules where requirements overlap; they need not form a strict inheritance hierarchy and must not redefine Core mechanics.
- **Primitive logic:** reusable transformations over declared inputs and outputs. Its contract declares whether and under which constraints it is incrementally processable, including buffering, lookahead, seek, materialization, and output-start requirements.
- **Runtime:** loading, scheduling, sandboxing, allocation policy, effects, resource limits, and stream orchestration—including transport, buffering, backpressure, cancellation, and chunk movement between primitives.
- **Registry:** source identity, manifests, contracts, tests, artifact identities, versions, and activation state.
- **Planner:** capability discovery and typed composition.
- **Ingress/egress:** translation between external systems and the internal vBuf domain.

Do not put runtime policy into vBuf formats or primitive logic. Persistent representation, runtime representation, and backend representation are distinct.

## Native shared-library artifacts

A compiled `.so` is intended to be a **downloadable, content-addressed, loadable capability artifact**. It should encapsulate reusable logic, not Bloom-runtime-specific behavior.

Semantic capability identity is independent of physical artifact packaging. One immutable artifact may provide multiple fine-grained capabilities, and packaging may later split or merge without changing their contracts. The registry remains authoritative for discovery; native descriptors may verify registry claims after admission but must not turn loading arbitrary binaries into discovery. Bundling is an implementation/distribution optimization, and only capabilities with compatible artifact-level trust, dependency, effect, and execution requirements should share a native artifact because admission applies to the whole binary.

### Required direction

- Expose primitives through a small, stable, versioned ABI rather than linking against runtime internals.
- Prefer capability/feature-based compatibility where practical rather than relying solely on exact ABI-version equality; keep the negotiation mechanism as open design work.
- Prefer a C-compatible ABI for the dynamic-library calling boundary, even when implementation code uses another language. This host ABI does not define the persistent vBuf wire/storage representation: compiler layouts, padding, pointers, and object representations are not canonical vBuf encoding.
- The public native ABI must be expressible entirely with C-compatible fixed-width primitives, pointers with explicit native span sizes, opaque contexts/handles, and carefully versioned flat POD structures only when unavoidable. Rust/C++/Go/Python and other language-native containers, fat pointers, classes, allocator objects, exceptions, and result types never cross it.
- Fix the target C calling convention for exported functions and callbacks where a platform offers alternatives. No panic, exception, or language unwind may cross the ABI; translate failures to explicit status before returning.
- Pass data through ABI-defined vBuf views, checked ranges, handles, and explicit result/error types.
- Keep primitive code independent of registry clients, planners, HTTP/MCP, CLI handling, process management, sandbox setup, logging frameworks, and runtime scheduling.
- Do not let a primitive reach into runtime-owned internal structs or rely on undocumented symbol layouts.
- Make ownership and lifetime explicit. Avoid requiring caller and library to share language-specific allocators or object models.
- Put host services behind explicit, versioned imports/callback tables when they are unavoidable. Capabilities such as filesystem, network, clock, randomness, and process execution must be declared and enforceable.
- Pure primitives should require no effectful host services.
- Treat resources and effects separately: CPU, temporary workspace, output bandwidth, and memory budgets are not filesystem/network/process permissions. Do not evade a missing workspace-allocation contract with unbounded stack allocation, fixed global buffers, direct OS allocation, undeclared allocator imports, or pathological recomputation. Count-proportional workspace must be host-owned, explicitly bounded, failure-aware, and lifetime-scoped before allocation-heavy primitives are admitted. Prefer one pre-sized invocation range over an allocator or public `free()` until a real capability proves otherwise.
- Keep configure/process/finalize state behind opaque ABI handles when a streaming primitive needs state.
- Treat annotations, views, and transformations distinctly so unchanged payload ranges can be reused without forced copying.

### Portability and distribution

A `.so` is not universally portable. Artifact identity and registry metadata must include its target constraints, including at least architecture, operating system, ABI/libc expectations, and Bloom primitive ABI version. Publish separate immutable artifacts per target when necessary; WASM or another portable artifact format may be used where broader portability or stronger isolation is required.

A downloadable artifact must be accompanied by machine-readable metadata covering:

- content hash and source revision;
- primitive name and semantic version/contract version;
- target triple and binary format;
- required Bloom ABI version;
- input/output contracts;
- streaming and materialization properties;
- declared effects and required host imports;
- determinism guarantees;
- resource expectations or limits where known;
- test/validation provenance.

Downloading, publication, and activation are separate operations. Never activate an artifact merely because its source was pushed or its binary was downloaded.

### Trust model

Downloaded native libraries are untrusted code. Before publication or activation, require isolated builds, validation, tests, artifact hashing, and policy checks. Loading a `.so` in the runtime process is not a security boundary; untrusted native artifacts need an appropriate sandbox or isolated worker. Do not weaken this model for convenience.

## Primitive design rules

A primitive should be:

- general-purpose and semantically coherent;
- composable and independently testable;
- explicitly typed;
- deterministic where practical;
- explicit about side effects;
- explicit about streaming, buffering, lookahead, seek, and materialization requirements;
- free of unnecessary domain or deployment policy.

Avoid both instruction-sized tools and one-off application binaries. Persist a commonly reused composition as an execution plan unless it represents a genuinely missing general capability.

## Data and execution rules

- Keep data in the vBuf domain through a pipeline when practical.
- Do not rewrite opaque payloads merely to add metadata.
- Prefer views/ranges and scatter-gather emission over copies.
- Preserve nested-root relocatability and local namespaces.
- Stream incrementally where semantics permit.
- Model global operations such as sorting as explicit materialization barriers.
- Do not encode values that are uniquely and cheaply derivable from existing structure.
- Keep large payloads out of JSON control calls and model context.

## Registry and reproducibility

Keep source, artifact, and active runtime state separate:

```text
source revision -> isolated build -> tested immutable artifact -> explicit activation
```

Use content identities for artifacts and deterministic results. A deterministic cache key should account for the exact tool artifact, arguments, and input content identities.

Before adding a primitive, document:

1. the capability gap;
2. search results for overlapping tools;
3. why composition is insufficient;
4. why an existing primitive should not be generalized;
5. the proposed reusable contract;
6. its expected semantic relationship to overlapping primitives (for example, orthogonal, specialization, generalization, replacement, or supersession).

## Development workflow

Because the implementation is still greenfield:

1. Inspect the repository and `README.md` before acting.
2. State assumptions when introducing foundational choices.
3. Prefer a narrow vertical slice over broad scaffolding.
4. Define and test contracts before adding convenience layers.
5. Add tests with every behavior change, including malformed inputs and ABI/version mismatches.
6. Test streaming in small chunks, ownership/lifetime boundaries, deterministic behavior, and effect denial.
7. Document build and test commands when they first exist; do not invent commands for tooling that has not been added.
8. Keep changes focused and update this file when a settled architectural decision changes agent guidance.

For ABI work, include compatibility tests that load an artifact through only the public ABI. Tests must catch accidental dependencies on runtime-private symbols and reject incompatible ABI versions or targets cleanly.

## Decision criteria

When alternatives are equivalent, prefer the design that:

1. reduces future model reasoning;
2. improves reuse and composability;
3. moves or copies less data;
4. makes contracts and effects easier to enforce;
5. improves deterministic testing and caching;
6. keeps the core and ABI smaller;
7. preserves the option to run primitives in process, in an isolated native worker, or as WASM.

## Do not

- Couple primitive implementations to one Bloom runtime implementation.
- Treat `.so` as a universal cross-platform artifact.
- Load arbitrary downloaded native code without validation and isolation.
- Mix registry publication with runtime activation.
- Add domain semantics to vBuf Core.
- Hide filesystem, network, clock, randomness, or process access.
- Force full payload materialization for metadata-only changes.
- Create near-duplicate primitives without registry search and semantic comparison.
- Claim functionality described in `README.md` is implemented unless code and tests demonstrate it.

## Open design work

The README defines direction, not a finalized wire or plugin ABI. The first implementation touching native artifacts should explicitly specify and review:

- the exact version/capability-negotiation and symbol-discovery mechanism;
- vBuf view/range layouts at the ABI boundary;
- ownership, allocation, cancellation, and error conventions;
- host import/capability tables;
- artifact manifest schema and target naming;
- native sandbox/worker strategy;
- compatibility and deprecation policy.

Do not silently lock these choices in through incidental implementation details.
