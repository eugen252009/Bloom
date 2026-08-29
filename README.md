# Bloom

**Bloom** is a vBuf-based, self-extending tool and agent ecosystem built around one central idea:

> Repeated AI reasoning should compound into persistent, reusable software capabilities instead of being paid for again in every session.

Bloom reduces the amount of software an agent has to generate from scratch.

Instead of asking a model to repeatedly build complete programs—including parsing, serialization, transport, memory handling, error handling, execution infrastructure, and integration code—Bloom provides a constrained environment of small, reusable primitives connected through a common binary processing ABI.

The model primarily decides:

```text
What do I have?
What do I need?
Which existing capabilities connect the two?
```

If the required capability does not yet exist, the system can create, validate, compile, register, and reuse a new general-purpose primitive.

Over time, ephemeral reasoning becomes persistent executable capability.

## Current implementation

Bloom currently provides one narrow Linux vertical slice: a local `bloom` CLI, a checked local JSON catalog, authoritative vBuf Core v0.6 input validation, and the pure native `bytes.identity`, `math.min.u32`, and `math.argmin.u32` artifacts loaded through public ABI v1. The math capabilities operate on canonical unsigned-u32 array blocks: reductions return the minimum or its stable first position, and `math.argsort.u32` returns a stable u64 permutation through the host-owned workspace path. Their exact contracts are documented in [`docs/math-min-u32.md`](docs/math-min-u32.md), [`docs/math-argmin-u32.md`](docs/math-argmin-u32.md), and [`docs/math-argsort-u32.md`](docs/math-argsort-u32.md). The implemented commands are `capabilities`, `describe`, and binary-safe `run`. Stable `math.argsort.u32` is implemented and registered through the separately versioned workspace execution family; its contract is documented in [`docs/math-argsort-u32.md`](docs/math-argsort-u32.md). The workspace qualification and ABI details remain in [`docs/workspace-qualification.md`](docs/workspace-qualification.md) and [`docs/workspace-abi-spec.md`](docs/workspace-abi-spec.md).

This first slice executes locally trusted `.so` artifacts in process. The public calling boundary is language-neutral C ABI v1, verified with C and test-only Rust artifacts on native x86_64 Linux and under executable AArch64 Linux GNU emulation; AArch64 artifacts are not published capabilities, and Windows/macOS loading is qualified but not implemented. It does not yet implement sandboxing, remote distribution, HTTP/MCP, planning, WASM execution, or the broader self-extending ecosystem described below. See [`docs/development.md`](docs/development.md) for verified build and usage commands, [`docs/primitive-abi-v1.md`](docs/primitive-abi-v1.md) for the calling boundary, and [`docs/native-abi-portability.md`](docs/native-abi-portability.md) for the portability qualification.

---

## Why "Bloom"?

Bloom sits at the transition between the outside world and the internal processing system.

```text
external data / requests / agents
              │
              ▼
            Bloom
              │
              ▼
      internal vBuf domain
              │
              ▼
     reusable tool pipelines
```

External formats, services, streams, and requests enter through Bloom and are translated into a common internal processing environment.

Once data has entered that environment, it should remain there for as much of the processing pipeline as possible.

---

# Core Idea

Conventional agent workflows often look like this:

```text
Task
 ↓
LLM reasoning
 ↓
generate temporary code
 ↓
parse input
 ↓
process
 ↓
serialize output
 ↓
discard implementation
```

A later task may trigger almost the same process again.

Bloom instead aims for:

```text
Task
 ↓
Capability Discovery
 ↓
Compose Existing Primitives
 ↓
Execute
```

If something is missing:

```text
Capability Gap
 ↓
Generate Minimal General Primitive
 ↓
Validate
 ↓
Test
 ↓
Compile
 ↓
Register
 ↓
Reuse Forever
```

This creates a compounding process:

```text
Tokens
  ↓
Reasoning
  ↓
Execution Plans
  ↓
Primitives
  ↓
Build Artifacts
  ↓
Reusable Capabilities
  ↓
Less Future Reasoning
```

This is the project's central concept:

## Token-to-Asset Compounding

---

# Architecture

```text
+-----------------------------------------------------------------------+
| External World                                                        |
|                                                                       |
| Files | stdin | HTTP | TCP | MCP | Agents | Services                  |
+----------------------------------+------------------------------------+
                                   |
                                   ▼
+-----------------------------------------------------------------------+
| Bloom                                                                 |
|                                                                       |
| Ingress / Egress                                                      |
| Capability Discovery                                                  |
| Pipeline Planning                                                     |
| Tool Composition                                                      |
+----------------------------------+------------------------------------+
                                   |
                                   ▼
+-----------------------------------------------------------------------+
| Tool Registry                                                         |
|                                                                       |
| Git Sources                                                           |
| Manifests                                                             |
| Tests                                                                 |
| Build Artifacts                                                       |
| Versions                                                              |
| Capability Metadata                                                   |
+----------------------------------+------------------------------------+
                                   |
                                   ▼
+-----------------------------------------------------------------------+
| Runtime                                                               |
|                                                                       |
| Process / Native / WASM Execution                                     |
| Sandboxing                                                            |
| Resource Limits                                                       |
| Streaming                                                             |
| Backpressure                                                          |
| Range-backed I/O                                                      |
+----------------------------------+------------------------------------+
                                   |
                                   ▼
+-----------------------------------------------------------------------+
| vBuf ABI                                                              |
|                                                                       |
| Metadata | Nested vBuf | Checked Ranges | Opaque Payloads             |
+----------------------------------+------------------------------------+
                                   |
                                   ▼
+-----------------------------------------------------------------------+
| Primitive Tool Layer                                                  |
|                                                                       |
| Decode | Filter | Transform | Analyze | Encode | Transport            |
+-----------------------------------------------------------------------+
```

---

# vBuf as the Internal ABI

Bloom uses **vBuf** as its common internal processing substrate.

The purpose is not to force every payload into a new physical representation.

Instead, vBuf provides a stable structural envelope around data.

For example:

```text
vBuf
├── type information
├── metadata
├── processing metadata
└── payload
    └── MP4 / JPEG / CSV / JSON / tensors / arbitrary bytes
```

The underlying payload may remain completely unchanged.

A 20 GB MP4 file does not need to become a 20 GB Bloom-specific video representation merely to move through the system.

The vBuf structure can describe what the payload is and how it should be interpreted while the payload itself remains opaque.

---

# Persistent Processing Representation

Once external data has entered the internal vBuf domain, Bloom attempts to keep it there until processing is complete.

Instead of:

```text
CSV
 ↓ parse
objects
 ↓ serialize
JSON
 ↓ parse
objects
 ↓ serialize
temporary format
 ↓ parse
...
```

Bloom aims for:

```text
External Input
      ↓
     vBuf
      ↓
   Primitive
      ↓
     vBuf
      ↓
   Primitive
      ↓
     vBuf
      ↓
   Primitive
      ↓
External Output
```

The internal representation does not need to be reconstructed between every operation.

---

# Nested vBuf

vBuf supports recursive nested roots.

```text
vBuf
├── metadata
└── nested vBuf
    ├── metadata
    └── nested vBuf
        └── payload
```

Each nested root has its own local geometry and namespace.

Nested child streams can therefore remain independently valid and relocatable.

A child may be:

```text
embedded inside a parent
```

and later extracted as:

```text
child.vbuf
```

without rewriting its internal structure.

This makes nested roots natural boundaries for:

```text
sharding
caching
large datasets
model components
stream sections
external storage
distributed processing
```

---

# Local Namespaces

A single vBuf root has a local 16-bit KeyID space.

That limit applies per root, not globally.

```text
Root
├── local keyspace
├── Child A
│   └── independent local keyspace
├── Child B
│   └── independent local keyspace
└── Child C
    └── independent local keyspace
```

This allows very large hierarchical structures without requiring large global identifiers throughout the format.

The principle is:

> Small local identifiers, recursively composed.

---

# Streaming

Bloom is designed around incremental processing wherever an operation allows it.

A typical stream-oriented tool can operate in three phases:

```text
Configure
   ↓
Process
   ↓
Finalize
```

## Configure

The tool reads the structural prefix and relevant metadata.

This may already be enough to determine:

```text
input type
output type
processing path
buffer requirements
decoder
encoder
runtime flags
```

## Process

Payload data can then be processed incrementally:

```text
stdin
  ↓
read chunk
  ↓
transform
  ↓
stdout
```

## Finalize

The tool completes any remaining state:

```text
flush
checksum completion
trailer emission
final state
```

---

# Real Pipeline Execution

Because tools can read stdin while writing stdout, an entire chain may execute concurrently.

```text
Source
  ↓
Tool A
  ↓
Tool B
  ↓
Tool C
  ↓
Sink
```

Conceptually:

```text
time ───────────────────────────────►

A: [HDR][1][2][3][4][5][6][7]
B:      [HDR][1][2][3][4][5][6]
C:           [HDR][1][2][3][4][5]
```

The full output of Tool A does not need to exist before Tool B begins.

For suitable workloads, total throughput therefore approaches the throughput of the slowest pipeline stage instead of forcing every stage to execute sequentially over the complete dataset.

---

# No Mandatory Payload Reallocation

Adding metadata does not require rewriting or moving the original payload.

A tool may logically produce:

```text
[new header]
[new metadata]
[existing payload]
```

without first allocating a new contiguous buffer containing everything.

The runtime may internally represent output as:

```text
Inline(header)
Inline(metadata)
Range(existing_source)
```

and later emit those segments sequentially.

Platform mechanisms may include:

```text
writev
sendmsg
sendfile
mmap
scatter/gather I/O
```

The canonical serialized form is still a normal linear vBuf stream.

The optimization exists in how that stream is produced.

---

# Tool Primitives

Bloom favors small, coherent, reusable operations.

Examples:

```text
decode.csv
decode.json

filter.rows
project.columns
sort
join
aggregate

regex.replace
tokenize

encode.json
encode.csv
```

A primitive should ideally be:

```text
general-purpose
composable
independently testable
deterministic where possible
free of unnecessary domain policy
explicitly typed
```

Bloom does not aim for microscopic instruction-level tools.

Bad:

```text
read-byte
compare-byte
increment-counter
write-byte
```

It also avoids monolithic one-off tools.

Bad:

```text
clean-customer-csv-and-generate-project-x-report
```

Prefer:

```text
decode.csv
validate.address
filter.rows
aggregate
encode.json
```

---

# Reuse Before Creation

The agent should not create a new tool simply because code generation is possible.

Before creating a primitive:

```text
Does the capability already exist?
        ↓ no

Can existing primitives be composed?
        ↓ no

Can an existing primitive be generalized?
        ↓ no

What is the smallest missing general capability?
```

Only then should new code be produced.

This is essential to prevent uncontrolled tool accumulation.

---

# Execution Plans

A reusable workflow does not automatically need to become another executable binary.

For example:

```text
decode.csv
→ filter.rows
→ project.columns
→ sort
→ encode.json
```

may simply become a persisted execution plan.

Bloom therefore distinguishes between:

```text
1. Reusing a primitive
2. Dynamically composing primitives
3. Persisting a composition as a plan
4. Creating a new general primitive
5. Building a domain-specific application only when necessary
```

This keeps the capability space small and orthogonal.

---

# Capability Registry

The registry should eventually represent more than tool names.

Each primitive can expose a machine-readable contract.

Conceptually:

```json
{
  "name": "filter.rows",
  "input": {
    "kind": "table"
  },
  "output": {
    "kind": "table"
  },
  "deterministic": true,
  "streaming": {
    "input": true,
    "output": true
  },
  "effects": {
    "filesystem": false,
    "network": false
  }
}
```

Additional metadata may include:

```text
schema requirements
ordering guarantees
memory bounds
lookahead
seek requirements
side effects
supported vBuf supersets
```

---

# Capability Graph

From these contracts, Bloom can build a graph of valid transformations.

```text
decode.csv
CSV → Table

filter.rows
Table → Table

aggregate
Table → AggregateTable

encode.json
Table → JSON
```

The planner can determine whether:

```text
Output(A) is compatible with Input(B)
```

and search for possible paths between a known input and desired output.

This reduces how much information the LLM itself must carry.

---

# Smaller Models

A conventional coding agent may need to reason about all of the following simultaneously:

```text
programming language
libraries
file parsing
serialization
memory management
error handling
filesystem access
network access
CLI design
process execution
testing
deployment
```

Bloom moves much of this complexity into the infrastructure.

The model may instead receive:

```text
Input:
Table<Customer>

Goal:
JSON<CustomerSummary>

Available:
filter.rows
project.columns
sort
aggregate
encode.json
```

Its remaining problem becomes:

```text
Which operations transform this input into the desired result?
```

This is a substantially smaller search space.

The hypothesis is that this can allow smaller models to produce significantly more reliable results than when they are asked to generate complete applications from scratch.

---

# Context Reduction

Tool discovery should also be selective.

A model should not need the complete documentation for hundreds or thousands of primitives in context.

Instead:

```text
Goal
 ↓
Registry Search
 ↓
small relevant capability set
 ↓
LLM planning
```

The model may only receive the five or ten tools relevant to the current transformation.

This reduces:

```text
context size
tool confusion
API hallucination
reasoning complexity
unnecessary token use
```

---

# Self-Extending Capability Space

When a capability genuinely does not exist, Bloom may allow an agent to create one.

The intended lifecycle is:

```text
Capability Gap
      ↓
Primitive Proposal
      ↓
Implementation
      ↓
Git Commit
      ↓
Isolated Build
      ↓
Validation
      ↓
Tests
      ↓
Immutable Artifact
      ↓
Registry Publication
```

Generated code does not become trusted simply because an agent produced it.

---

# Git-Native Registry

Git acts as the source of truth for primitive implementations.

Example:

```text
tools/
├── .registry/
│   └── index.json
├── decode/
│   └── csv/
│       ├── manifest.json
│       ├── README.md
│       ├── tests/
│       └── src/
├── filter/
│   └── rows/
└── encode/
    └── json/
```

Git naturally provides:

```text
history
versioning
diffs
rollback
review
branches
content identity
```

---

# Source, Artifact, and Runtime State

Source code and active executable tools should remain separate concepts.

```text
Source Registry
      ↓
Git Commit

Artifact Registry
      ↓
built Binary / WASM / library

Runtime Registry
      ↓
currently activated version
```

For example:

```text
source:
7ac839...

artifact:
sha256:93ab...

runtime:
filter.rows@7ac839
```

A source push must not automatically imply activation.

---

# Build Isolation

The build process itself is untrusted execution.

Build systems can execute code through:

```text
build.rs
Makefile
CMake
package scripts
compiler plugins
```

Therefore:

```text
Git Push
   ↓
Validation
   ↓
Isolated Build Worker
   ↓
Tests
   ↓
Artifact Hash
   ↓
Publication
   ↓
Activation
```

The Git server itself should execute as little build logic as possible.

---

# Pure and Effectful Tools

Bloom distinguishes deterministic computation from external side effects.

Examples:

```text
filter.rows
PURE

sort
PURE

regex.replace
PURE

http.fetch
NETWORK EFFECT

file.write
FILESYSTEM EFFECT

smtp.send
EXTERNAL SIDE EFFECT
```

Capabilities can be declared and enforced by the runtime.

Example:

```text
filesystem:
    read: input
    write: output

network:
    false

process:
    false

clock:
    false
```

---

# Determinism

Deterministic tools are preferred wherever practical.

Conceptually:

```text
Input + Tool + Arguments
        ↓
same Result
```

This enables:

```text
reproducible tests
debugging
memoization
deduplication
distributed execution
result caching
```

Non-deterministic behavior should be explicit.

---

# Deterministic Result Reuse

A deterministic result can conceptually be identified by:

```text
Result ID =
hash(
    tool artifact,
    arguments,
    input content identities
)
```

If the same operation has already been performed, the previous result may be reused.

The compounding chain therefore becomes:

```text
Reasoning
   ↓
Execution Plan
   ↓
Primitive
   ↓
Artifact
   ↓
Cached Result
```

Bloom attempts to avoid paying twice wherever stable computation can become a reusable asset.

---

# Streaming and Materialization Barriers

Not every operation can be processed incrementally.

For example:

```text
filter
→ streamable

map
→ streamable

regex replace
→ potentially bounded lookahead

sort
→ global barrier

median
→ global or partially global information

reverse
→ requires random access or full materialization
```

A primitive should therefore be able to declare properties such as:

```text
input_streaming
output_streaming
lookahead
buffer_bound
requires_seek
output_start
```

The planner can then identify where a pipeline remains fully streaming and where materialization is unavoidable.

---

# Data Movement Classes

Bloom can distinguish operations according to how they affect the underlying payload.

## Annotation

```text
new metadata
+
unchanged payload
```

## View

```text
new logical interpretation
+
existing payload range
```

Examples include:

```text
slice
subset
projection
range
```

## Transformation

The payload itself changes.

Examples:

```text
compression
image resize
video transcode
numeric conversion
```

Where equivalent approaches exist, the runtime or planner can prefer operations that move less data.

---

# vBuf Core and Supersets

Bloom does not require vBuf Core to understand tool semantics.

The intended layering is:

```text
vBuf Core
├── canonical blocks
├── checked ranges
├── local geometry
├── alignment
├── opaque payloads
├── continuation
├── indefinite streams
├── generic extensions
└── recursive nested vBuf roots
```

Domain-specific semantics live above the Core.

For example:

```text
vBuf-ML
├── tensors
├── models
├── tokenizers
├── quantization
└── ML-specific structural semantics
```

Bloom may define its own tool-oriented superset:

```text
vBuf-Tool
├── typed tool envelopes
├── tool contracts
├── execution plans
├── streaming declarations
├── effect declarations
└── capability metadata
```

Supersets may overlap where their requirements overlap.

They do not need to form a strict inheritance hierarchy.

---

# vBuf-ML as a Reference Example

vBuf-ML follows the same general philosophy.

It remains deliberately declarative.

It describes enough structure for a runtime to efficiently construct the representation required by an execution backend.

It does not attempt to encode runtime policy itself.

The distinction is:

```text
persistent representation
        !=
runtime representation
        !=
backend representation
```

Information that can be derived uniquely and cheaply from existing structure does not need to be persisted redundantly.

The runtime may reconstruct richer views when required.

Bloom applies the same principle outside machine learning.

---

# MCP and HTTP

MCP and HTTP are control and integration surfaces, not the primary large-data path.

An agent may request:

```json
{
  "tool": "filter.rows",
  "source": "artifact:83fa...",
  "arguments": {
    "column": "status",
    "equals": "active"
  }
}
```

The actual large payload remains within the runtime and vBuf processing path.

The model should not need to shuttle gigabytes of data through JSON tool calls or context.

---

# Unix Composition

For humans, Bloom should remain compatible with simple Unix-style composition.

Example:

```bash
cat customers.csv \
  | bloom-decode-csv \
  | bloom-filter --column=status --eq=active \
  | bloom-project --columns=id,name,revenue \
  | bloom-sort --column=revenue --desc \
  | bloom-encode-json
```

After the initial ingress transformation, the data can remain within the internal vBuf representation throughout the pipeline.

---

# The Accretion Problem

A self-extending system can become useless if it continuously creates semantically duplicate tools.

Without controls, the registry may eventually contain:

```text
filter.rows
table.filter
where
row.select
predicate.filter
select.where
```

all implementing essentially the same capability.

New primitives should therefore go through a proposal process:

```text
SEARCH
  ↓
COMPARE SEMANTICS
  ↓
CAN COMPOSE EXISTING TOOLS?
  ↓
CAN GENERALIZE AN EXISTING TOOL?
  ↓
CREATE ONLY IF NECESSARY
```

A proposal may also record:

```text
why existing tools are insufficient
semantic overlap
intended generalization
```

The goal is not to maximize tool count.

The goal is to maximize useful compositional capability.

---

# Executable Knowledge

Bloom ultimately treats software artifacts as a form of persistent knowledge.

Knowledge exists as:

```text
tested primitives
typed contracts
validated execution plans
build artifacts
cached deterministic results
```

The LLM does not need to reconstruct this knowledge from tokens every time it is needed.

This changes the role of the model.

Instead of being the entire implementation environment, the model becomes primarily a semantic planner operating over an executable capability space.

---

# Central Hypothesis

Bloom is based on the hypothesis that:

> The practical capability of an AI system is determined not only by model size, but also by the structure and constraints of the environment in which the model operates.

A smaller model with:

```text
a constrained tool space
+
strong contracts
+
reusable primitives
+
deterministic execution
+
persistent plans
+
selective capability discovery
```

may outperform the same model when asked to repeatedly generate arbitrary complete programs.

The intelligence of the overall system is therefore distributed across:

```text
LLM
+
Capability Registry
+
Primitive Library
+
Execution Plans
+
Runtime
+
Persistent Artifacts
```

---

# Evaluation

This hypothesis should be measured rather than assumed.

A useful benchmark can compare the same model in two environments.

## Conventional Agent

```text
shell
compiler
filesystem
arbitrary code generation
```

## Bloom

```text
vBuf ABI
capability registry
primitive library
typed planner
constrained code generation
```

Relevant metrics include:

```text
Task Success Rate
Token Usage
Tool Calls
Failed Attempts
Generated Lines of Code
Execution Time
Peak Memory
Data Movement
Primitive Reuse
Primitive Creation Rate
Plan Reuse
Cache Hit Rate
```

A particularly important metric is:

> How much useful task complexity can a smaller model reliably handle once the surrounding solution space is strongly structured?

---

# Design Principles

Bloom follows a small set of architectural rules.

### Keep vBuf Core Minimal

The Core defines structural mechanics, not application semantics.

### Reuse Before Generation

Existing capabilities and compositions are preferred over new code.

### Persist Stable Reasoning

Repeatedly useful logic should become an artifact.

### Structure Before Materialization

Navigate and reference data where possible instead of reconstructing it.

### Stream Where Possible

Full materialization should happen only when semantically necessary.

### Avoid Redundant Representation

Do not persist information that can be derived uniquely and cheaply.

### Keep Tools Orthogonal

Tools should implement coherent reusable operations.

### Separate Capabilities from Artifact Packaging

Agents and planners reason about fine-grained semantic capabilities, not library bundles. One immutable artifact may provide multiple compatible capabilities; artifacts may later be split or merged without changing capability identities or contracts. Bundling is an implementation and distribution optimization, while registry declarations remain authoritative and native admission applies to the whole physical artifact.

### Make Effects Explicit

Filesystem, network, process, clock, randomness, and other effects should be declared.

### Prefer Determinism

Deterministic computation is easier to test, cache, audit, and reuse.

### Keep Runtime Intelligence Out of the Format

Formats describe structure and semantics.

Runtimes decide execution strategy.

---

# Long-Term Model

The intended system ultimately looks like this:

```text
                      User / Agent
                           │
                           ▼
                    Requested Goal
                           │
                           ▼
                  Capability Discovery
                           │
                           ▼
                     Typed Planning
                           │
                           ▼
                    Execution Plan
                           │
                           ▼
                Bloom Runtime / Sandbox
                           │
                           ▼
                       vBuf ABI
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
         Primitive A   Primitive B   Primitive C
             │             │             │
             └─────────────┬─────────────┘
                           ▼
                         Result
                           │
                           ▼
                  Persistent Reuse
```

When something is missing:

```text
Capability Gap
      ↓
Primitive Proposal
      ↓
Implementation
      ↓
Isolated Build
      ↓
Validation
      ↓
Registry
      ↓
Future Reuse
```

---

# Summary

Bloom is not intended to be another general-purpose coding agent.

It is an environment designed to make agents need less arbitrary code generation over time.

Its core strategy is:

```text
convert external data into a common processing domain
                       ↓
discover reusable capabilities
                       ↓
compose deterministic primitives
                       ↓
persist useful plans and missing capabilities
                       ↓
reuse them in future tasks
```

vBuf provides the structural substrate.

The registry provides persistent capability discovery.

The runtime provides safe and efficient execution.

The LLM provides semantic planning.

Together they form a system in which temporary reasoning can gradually become permanent executable infrastructure.

The objective is not merely to make individual AI calls cheaper.

The objective is to make the system itself increasingly capable without requiring the model to relearn or regenerate the same solutions indefinitely.
