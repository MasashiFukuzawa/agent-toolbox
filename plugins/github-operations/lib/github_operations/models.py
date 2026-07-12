from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Identity:
    host: str
    login: str
    node_id: str


@dataclass
class Plan:
    schema_version: int
    plan_id: str
    domain: str
    action: str
    created_at: str
    expires_at: str
    identity: dict[str, str]
    target: str
    config_path: str
    config_digest: str
    observed_digest: str
    observed: dict[str, Any]
    request: dict[str, Any]
    operations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
