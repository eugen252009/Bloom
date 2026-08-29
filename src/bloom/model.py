from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Artifact:
    format: str
    identity: str
    path: Path
    target: str
    abi_base: int


@dataclass(frozen=True)
class ExecutionBinding:
    family: str
    version: int
    query: str
    run: str


@dataclass(frozen=True)
class Capability:
    name: str
    contract_version: str
    available: bool
    artifact: Artifact
    input: dict[str, Any]
    output: dict[str, Any]
    deterministic: bool
    effects: tuple[str, ...]
    streaming: dict[str, Any]
    execution: ExecutionBinding | None = None

    def describe(self) -> dict[str, Any]:
        result = {
            "name": self.name,
            "contract_version": self.contract_version,
            "available": self.available,
            "artifact": {
                "format": self.artifact.format,
                "identity": self.artifact.identity,
                "path": str(self.artifact.path),
                "target": self.artifact.target,
                "bloom_primitive_abi": {"base": self.artifact.abi_base},
            },
            "input": self.input,
            "output": self.output,
            "deterministic": self.deterministic,
            "effects": list(self.effects),
            "streaming": self.streaming,
        }
        if self.execution is not None:
            result["execution"] = {
                "family": self.execution.family,
                "version": self.execution.version,
                "query": self.execution.query,
                "run": self.execution.run,
            }
        return result
