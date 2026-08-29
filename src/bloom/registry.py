from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from .errors import RegistryError
from .model import Artifact, Capability, ExecutionBinding


class Catalog(Protocol):
    def list(self) -> list[Capability]: ...
    def describe(self, name: str) -> Capability: ...
    def resolve(self, name: str) -> Capability: ...


def _object(value: Any, label: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RegistryError(f"catalog: {label} must be an object")
    unknown = set(value) - keys
    missing = keys - set(value)
    if unknown or missing:
        details = []
        if missing:
            details.append("missing " + ", ".join(sorted(missing)))
        if unknown:
            details.append("unknown " + ", ".join(sorted(unknown)))
        raise RegistryError(f"catalog: invalid {label}: {'; '.join(details)}")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RegistryError(f"catalog: {label} must be a non-empty string")
    return value


class LocalCatalog:
    """Checked schema-v1 catalog backed by one local JSON file."""

    def __init__(self, path: Path):
        self.path = path.resolve()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RegistryError(f"cannot read catalog {self.path}: {error}") from error
        root = _object(raw, "root", {"schema_version", "capabilities"})
        if root["schema_version"] != 1:
            raise RegistryError(
                f"catalog: unsupported schema_version {root['schema_version']!r}"
            )
        if not isinstance(root["capabilities"], list):
            raise RegistryError("catalog: capabilities must be an array")
        capabilities = [self._parse(item, index) for index, item in enumerate(root["capabilities"])]
        self._capabilities: dict[str, Capability] = {}
        for capability in capabilities:
            if capability.name in self._capabilities:
                raise RegistryError(f"catalog: duplicate capability {capability.name!r}")
            self._capabilities[capability.name] = capability

    def _parse(self, raw: Any, index: int) -> Capability:
        label = f"capabilities[{index}]"
        execution_present = isinstance(raw, dict) and "execution" in raw
        if isinstance(raw, dict) and not execution_present:
            raw = {**raw, "execution": None}
        item = _object(
            raw,
            label,
            {
                "name", "contract_version", "available", "artifact", "input",
                "output", "deterministic", "effects", "streaming", "execution",
            },
        )
        artifact_raw = _object(
            item["artifact"], f"{label}.artifact",
            {"format", "identity", "path", "target", "bloom_primitive_abi"},
        )
        abi = _object(
            artifact_raw["bloom_primitive_abi"],
            f"{label}.artifact.bloom_primitive_abi", {"base"},
        )
        if not isinstance(abi["base"], int) or isinstance(abi["base"], bool):
            raise RegistryError(f"catalog: {label} ABI base must be an integer")
        if not isinstance(item["available"], bool) or not isinstance(item["deterministic"], bool):
            raise RegistryError(f"catalog: {label} availability/determinism must be boolean")
        if not isinstance(item["effects"], list) or not all(
            isinstance(effect, str) and effect for effect in item["effects"]
        ):
            raise RegistryError(f"catalog: {label}.effects must be an array of strings")
        for field in ("input", "output", "streaming"):
            if not isinstance(item[field], dict):
                raise RegistryError(f"catalog: {label}.{field} must be an object")
        execution_raw = item.get("execution")
        execution = None
        if execution_present and execution_raw is None:
            raise RegistryError(f"catalog: {label}.execution must be an object")
        if execution_raw is not None:
            execution_raw = _object(
                execution_raw, f"{label}.execution", {"family", "version", "query", "run"}
            )
            if execution_raw["family"] != "workspace":
                raise RegistryError(f"catalog: {label}.execution.family must be 'workspace'")
            if not isinstance(execution_raw["version"], int) or isinstance(execution_raw["version"], bool):
                raise RegistryError(f"catalog: {label}.execution.version must be an integer")
            execution = ExecutionBinding(
                family="workspace", version=execution_raw["version"],
                query=_string(execution_raw["query"], f"{label}.execution.query"),
                run=_string(execution_raw["run"], f"{label}.execution.run"),
            )
        artifact_path = Path(_string(artifact_raw["path"], f"{label}.artifact.path"))
        if not artifact_path.is_absolute():
            artifact_path = (self.path.parent / artifact_path).resolve()
        artifact = Artifact(
            format=_string(artifact_raw["format"], f"{label}.artifact.format"),
            identity=_string(artifact_raw["identity"], f"{label}.artifact.identity"),
            path=artifact_path,
            target=_string(artifact_raw["target"], f"{label}.artifact.target"),
            abi_base=abi["base"],
        )
        return Capability(
            name=_string(item["name"], f"{label}.name"),
            contract_version=_string(item["contract_version"], f"{label}.contract_version"),
            available=item["available"], artifact=artifact,
            input=dict(item["input"]), output=dict(item["output"]),
            deterministic=item["deterministic"], effects=tuple(item["effects"]),
            streaming=dict(item["streaming"]), execution=execution,
        )

    def list(self) -> list[Capability]:
        return sorted(self._capabilities.values(), key=lambda item: item.name)

    def describe(self, name: str) -> Capability:
        try:
            return self._capabilities[name]
        except KeyError as error:
            raise RegistryError(f"unknown capability: {name}") from error

    def resolve(self, name: str) -> Capability:
        capability = self.describe(name)
        if not capability.available:
            raise RegistryError(f"capability is not locally available: {name}")
        return capability
