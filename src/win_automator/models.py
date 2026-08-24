from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Selector:
    backend: str = "uia"
    window_title: str = ""
    window_class: str = ""
    process_name: str = ""
    automation_id: str = ""
    control_type: str = ""
    name: str = ""
    class_name: str = ""
    control_id: Optional[int] = None
    parent_name: str = ""
    relative_x: Optional[float] = None
    relative_y: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["Selector"]:
        if not data:
            return None
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in data.items() if key in allowed})


@dataclass
class ValueSpec:
    source: str = "literal"  # literal | excel
    column: str = ""
    literal: Any = ""

    def resolve(self, row: Dict[str, Any]) -> Any:
        if self.source == "excel":
            return row.get(self.column, "")
        return self.literal

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["ValueSpec"]:
        if data is None:
            return None
        return cls(
            source=data.get("source", "literal"),
            column=data.get("column", ""),
            literal=data.get("literal", ""),
        )


@dataclass
class Step:
    action: str
    target: Optional[Selector] = None
    value: Optional[ValueSpec] = None
    key: str = ""
    timeout: float = 10.0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "action": self.action,
            "timeout": self.timeout,
        }
        if self.description:
            data["description"] = self.description
        if self.target:
            data["target"] = asdict(self.target)
        if self.value:
            data["value"] = asdict(self.value)
        if self.key:
            data["key"] = self.key
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Step":
        return cls(
            action=data["action"],
            target=Selector.from_dict(data.get("target")),
            value=ValueSpec.from_dict(data.get("value")),
            key=data.get("key", ""),
            timeout=float(data.get("timeout", 10.0)),
            description=data.get("description", ""),
        )


@dataclass
class Scenario:
    name: str = "Новый сценарий"
    version: int = 1
    steps: List[Step] = field(default_factory=list)
    mappings: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "steps": [step.to_dict() for step in self.steps],
            "mappings": self.mappings,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scenario":
        return cls(
            version=int(data.get("version", 1)),
            name=data.get("name", "Сценарий"),
            steps=[Step.from_dict(item) for item in data.get("steps", [])],
            mappings=data.get("mappings", {}) or {},
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> "Scenario":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
