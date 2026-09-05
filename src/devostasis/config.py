"""Project configuration, resolution of defaults and the effective config projection.

Every configuration input that can change canonical bundle members is either
already identity-bearing (class A), projected into ``effective_bundle_config``
(class B) or proven non-canonical (class C). An input that cannot be classified
fails closed with ``CONFIG_IDENTITY_UNCLASSIFIED`` (PV-EFFECTIVE-CONFIG-001).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import canonical
from .contracts import CORE_VITAL_IDS, EFFECTIVE_CONFIG_SCHEMA
from .demand import DEFAULT_LEVELS, DEFAULT_MAPPING_VERSION, LEVELS
from .vitals import BANDS

CONFIG_SCHEMA = "devostasis.config.v1"

PROJECT_KEY_CLASSIFICATION = {
    "provider": "A",
    "repo": "A",
    "planning": "B",
    "debt": "B",
    "report_html": "B",
    "locale": "B",
    "activity": "B",
    "observations_member": "B",
    "display": "B",
    "demand": "B",
    "display_name": "C",
    "notes": "C",
}

GLOBAL_KEY_CLASSIFICATION = {
    "schema": "A",
    "config_version": "A",
    "store": "C",
    "defaults": "B",
    "projects": "A",
    "token_env": "C",
    "user_agent": "C",
    "notes": "C",
}

PLANNING_SOURCES = ("milestones", "file", "none")
DEBT_SOURCES = ("labels", "file")
LOCALES = ("en",)
GAUGE_MODES = ("bar", "number", "band")
DISPLAY_SECTIONS = ("demand", "details", "observability", "changes", "activity", "provenance")

DEFAULTS: dict[str, Any] = {
    "planning": {"source": "milestones", "path": None, "link_marker": "Target:"},
    "debt": None,
    "report_html": False,
    "locale": "en",
    "activity": {"enabled": True, "list_cap": 50},
    "observations_member": True,
    "display": {"vitals": list(CORE_VITAL_IDS), "gauge": list(GAUGE_MODES), "sections": list(DISPLAY_SECTIONS)},
    "demand": {"mapping_version": DEFAULT_MAPPING_VERSION, "levels": {}},
}


class ConfigError(ValueError):
    """Raised for invalid configuration; CONFIG_IDENTITY_UNCLASSIFIED is one reason code."""


@dataclass(frozen=True)
class ResolvedProject:
    provider: str
    owner: str
    repo: str
    config_version: str
    planning: dict[str, Any]
    debt_mapping: dict[str, Any] | None
    report_html: bool
    locale: str
    activity_enabled: bool
    activity_list_cap: int
    observations_member: bool
    display: dict[str, Any]
    demand: dict[str, Any]
    display_name: str | None = None

    @property
    def locator(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def project_key(self) -> str:
        return f"github.com/{self.owner}/{self.repo}"

    @property
    def planning_source(self) -> str:
        return self.planning["source"]

    def effective_bundle_config(self) -> dict[str, Any]:
        """Schema-versioned projection of every canonical-output-affecting resolved value."""
        return {
            "schema": EFFECTIVE_CONFIG_SCHEMA,
            "planning": {
                "source": self.planning["source"],
                "path": self.planning.get("path"),
                "link_marker": self.planning.get("link_marker"),
            },
            "debt_mapping": None if self.debt_mapping is None else copy.deepcopy(self.debt_mapping),
            "report_html": "ENABLED" if self.report_html else "DISABLED",
            "locale": self.locale,
            "activity": "ENABLED" if self.activity_enabled else "DISABLED",
            "activity_list_cap": self.activity_list_cap,
            "observations_member": "ENABLED" if self.observations_member else "DISABLED",
            "display": {
                "vitals": list(self.display["vitals"]),
                "gauge": list(self.display["gauge"]),
                "sections": list(self.display["sections"]),
            },
            "demand": {
                "mapping_version": self.demand["mapping_version"],
                "levels": {vital: dict(sorted(table.items())) for vital, table in sorted(self.demand["levels"].items())},
            },
        }

    def semantic_config(self) -> dict[str, Any]:
        """Subset whose change makes Vital history incomparable."""
        effective = self.effective_bundle_config()
        return {"planning": effective["planning"], "debt_mapping": effective["debt_mapping"]}

    def effective_config_digest(self) -> str:
        return canonical.digest(self.effective_bundle_config())


@dataclass(frozen=True)
class Config:
    config_version: str
    store_path: str
    projects: tuple[ResolvedProject, ...]
    token_env: str | None = None
    user_agent: str | None = None


def _classify_keys(raw: dict[str, Any], registry: dict[str, str], scope: str) -> None:
    for key in raw:
        if key not in registry:
            raise ConfigError(f"CONFIG_IDENTITY_UNCLASSIFIED: {scope} key {key!r} is not classified as identity-bearing, projected or non-canonical")


def _merge_defaults(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key, value in defaults.items():
        merged[key] = copy.deepcopy(value)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = dict(merged[key], **value)
        else:
            merged[key] = value
    return merged


def _validate_planning(planning: Any) -> dict[str, Any]:
    if not isinstance(planning, dict):
        raise ConfigError("planning must be an object")
    for key in planning:
        if key not in ("source", "path", "link_marker"):
            raise ConfigError(f"CONFIG_IDENTITY_UNCLASSIFIED: planning key {key!r} is unknown")
    source = planning.get("source", "milestones")
    if source not in PLANNING_SOURCES:
        raise ConfigError(f"planning.source must be one of {PLANNING_SOURCES}, got {source!r}")
    path = planning.get("path")
    if source == "file":
        if not isinstance(path, str) or not path.strip() or path.startswith("/") or ".." in path.split("/"):
            raise ConfigError("planning.source = file requires a repository-relative planning.path")
    else:
        path = None
    marker = planning.get("link_marker", "Target:")
    if not isinstance(marker, str) or not marker.strip():
        raise ConfigError("planning.link_marker must be a non-empty string")
    return {"source": source, "path": path, "link_marker": marker}


def _validate_debt(mapping: Any) -> dict[str, Any] | None:
    if mapping is None:
        return None
    if not isinstance(mapping, dict):
        raise ConfigError("debt mapping must be an object or null")
    for key in mapping:
        if key not in ("source", "labels", "path", "mapping_version"):
            raise ConfigError(f"CONFIG_IDENTITY_UNCLASSIFIED: debt mapping key {key!r} is unknown")
    source = mapping.get("source") or ("file" if "path" in mapping and "labels" not in mapping else "labels")
    if source not in DEBT_SOURCES:
        raise ConfigError(f"debt.source must be one of {DEBT_SOURCES}, got {source!r}")
    version = mapping.get("mapping_version")
    if not isinstance(version, str) or not version:
        raise ConfigError("debt mapping requires a mapping_version string")
    if source == "labels":
        labels = mapping.get("labels")
        if not isinstance(labels, list) or not labels or not all(isinstance(item, str) and item for item in labels):
            raise ConfigError("debt mapping with source labels requires a non-empty list of label names")
        return {"source": "labels", "labels": sorted(set(labels)), "mapping_version": version}
    path = mapping.get("path")
    if not isinstance(path, str) or not path.strip() or path.startswith("/") or ".." in path.split("/"):
        raise ConfigError("debt mapping with source file requires a repository-relative path")
    return {"source": "file", "path": path, "mapping_version": version}


def _validate_display(display: Any) -> dict[str, Any]:
    if not isinstance(display, dict):
        raise ConfigError("display must be an object")
    for key in display:
        if key not in ("vitals", "gauge", "sections"):
            raise ConfigError(f"CONFIG_IDENTITY_UNCLASSIFIED: display key {key!r} is unknown")
    vitals = display.get("vitals", list(CORE_VITAL_IDS))
    if not isinstance(vitals, list) or not vitals or len(set(vitals)) != len(vitals) or any(v not in CORE_VITAL_IDS for v in vitals):
        raise ConfigError(f"display.vitals must be a non-empty list of distinct Vital ids from {CORE_VITAL_IDS}")
    gauge = display.get("gauge", list(GAUGE_MODES))
    if not isinstance(gauge, list) or not gauge or any(mode not in GAUGE_MODES for mode in gauge) or len(set(gauge)) != len(gauge):
        raise ConfigError(f"display.gauge must be a non-empty list of distinct modes from {GAUGE_MODES}")
    sections = display.get("sections", list(DISPLAY_SECTIONS))
    if not isinstance(sections, list) or any(section not in DISPLAY_SECTIONS for section in sections) or len(set(sections)) != len(sections):
        raise ConfigError(f"display.sections must be a list of distinct sections from {DISPLAY_SECTIONS}")
    return {"vitals": list(vitals), "gauge": [mode for mode in GAUGE_MODES if mode in gauge], "sections": [s for s in DISPLAY_SECTIONS if s in sections]}


def _validate_demand(demand: Any) -> dict[str, Any]:
    if not isinstance(demand, dict):
        raise ConfigError("demand must be an object")
    for key in demand:
        if key not in ("mapping_version", "levels"):
            raise ConfigError(f"CONFIG_IDENTITY_UNCLASSIFIED: demand key {key!r} is unknown")
    version = demand.get("mapping_version", DEFAULT_MAPPING_VERSION)
    if not isinstance(version, str) or not version:
        raise ConfigError("demand.mapping_version must be a non-empty string")
    overrides = demand.get("levels") or {}
    if not isinstance(overrides, dict):
        raise ConfigError("demand.levels must be an object of vital -> band -> level")
    levels = copy.deepcopy(DEFAULT_LEVELS)
    for vital, table in overrides.items():
        if vital not in CORE_VITAL_IDS:
            raise ConfigError(f"demand.levels: unknown Vital {vital!r}")
        if not isinstance(table, dict):
            raise ConfigError(f"demand.levels.{vital} must be an object of band -> level")
        for band, level in table.items():
            if band not in BANDS[vital]:
                raise ConfigError(f"demand.levels.{vital}: unknown band {band!r}")
            if level not in LEVELS:
                raise ConfigError(f"demand.levels.{vital}.{band}: level must be one of {LEVELS}, got {level!r}")
            levels[vital][band] = level
    if overrides and version == DEFAULT_MAPPING_VERSION:
        raise ConfigError("demand.levels overrides require an explicit demand.mapping_version")
    return {"mapping_version": version, "levels": levels}


def resolve_project(raw: dict[str, Any], defaults: dict[str, Any], config_version: str) -> ResolvedProject:
    if not isinstance(raw, dict):
        raise ConfigError("each project must be an object")
    _classify_keys(raw, PROJECT_KEY_CLASSIFICATION, "project")
    provider = raw.get("provider", "github")
    if provider != "github":
        raise ConfigError(f"unsupported provider {provider!r}; this version implements the GitHub adapter only")
    repo = raw.get("repo")
    if not isinstance(repo, str) or repo.count("/") != 1 or not all(repo.split("/")):
        raise ConfigError(f"project repo must be 'owner/name', got {repo!r}")
    owner, name = repo.split("/")
    projected = {k: v for k, v in raw.items() if PROJECT_KEY_CLASSIFICATION.get(k) == "B"}
    merged = _merge_defaults(defaults, projected)

    activity = merged.get("activity") or {}
    for key in activity:
        if key not in ("enabled", "list_cap"):
            raise ConfigError(f"CONFIG_IDENTITY_UNCLASSIFIED: activity key {key!r} is unknown")
    enabled = bool(activity.get("enabled", True))
    cap = activity.get("list_cap", 50)
    if not isinstance(cap, int) or isinstance(cap, bool) or cap < 0:
        raise ConfigError("activity.list_cap must be a non-negative integer")

    locale = merged.get("locale", "en")
    if locale not in LOCALES:
        raise ConfigError(f"locale must be one of {LOCALES}, got {locale!r}")
    report_html = merged.get("report_html", False)
    if not isinstance(report_html, bool):
        raise ConfigError("report_html must be a boolean")
    observations_member = merged.get("observations_member", True)
    if not isinstance(observations_member, bool):
        raise ConfigError("observations_member must be a boolean")

    return ResolvedProject(
        provider=provider,
        owner=owner,
        repo=name,
        config_version=config_version,
        planning=_validate_planning(merged.get("planning") or {}),
        debt_mapping=_validate_debt(merged.get("debt")),
        report_html=report_html,
        locale=locale,
        activity_enabled=enabled,
        activity_list_cap=cap,
        observations_member=observations_member,
        display=_validate_display(merged.get("display") or {}),
        demand=_validate_demand(merged.get("demand") or {}),
        display_name=raw.get("display_name"),
    )


def load_config_dict(raw: dict[str, Any], base_dir: Path | None = None) -> Config:
    if not isinstance(raw, dict):
        raise ConfigError("configuration root must be an object")
    _classify_keys(raw, GLOBAL_KEY_CLASSIFICATION, "global")
    if raw.get("schema", CONFIG_SCHEMA) != CONFIG_SCHEMA:
        raise ConfigError(f"unsupported config schema {raw.get('schema')!r}")
    config_version = raw.get("config_version")
    if not isinstance(config_version, str) or not config_version:
        raise ConfigError("config_version must be a non-empty string")
    defaults_raw = raw.get("defaults") or {}
    _classify_keys(defaults_raw, {k: v for k, v in PROJECT_KEY_CLASSIFICATION.items() if v == "B"}, "defaults")
    defaults = _merge_defaults(DEFAULTS, defaults_raw)
    projects_raw = raw.get("projects")
    if not isinstance(projects_raw, list) or not projects_raw:
        raise ConfigError("projects must be a non-empty list")
    projects = tuple(resolve_project(item, defaults, config_version) for item in projects_raw)
    seen = set()
    for project in projects:
        if project.project_key in seen:
            raise ConfigError(f"duplicate project {project.locator}")
        seen.add(project.project_key)
    store = raw.get("store") or {}
    store_path = store.get("path", ".") if isinstance(store, dict) else "."
    if base_dir is not None and not Path(store_path).is_absolute():
        store_path = str((base_dir / store_path).resolve())
    return Config(
        config_version=config_version,
        store_path=store_path,
        projects=projects,
        token_env=raw.get("token_env"),
        user_agent=raw.get("user_agent"),
    )


def load_config(path: str | Path) -> Config:
    path = Path(path)
    return load_config_dict(canonical.load_file(path), base_dir=path.parent)


def single_project(repo: str, config_version: str = "cli", **overrides: Any) -> ResolvedProject:
    """Resolve one project from CLI arguments with default configuration."""
    raw: dict[str, Any] = {"provider": "github", "repo": repo}
    raw.update(overrides)
    return resolve_project(raw, DEFAULTS, config_version)
