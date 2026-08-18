"""Track B freeze artifact loading and M1A execution gates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml

VALID_STRUCTURAL_STATUSES = frozenset({"pass", "pass_with_warning"})
SUPPORTED_DATASET_FINGERPRINT_ALGORITHM = "track-b-daily-sha256-v1"
SUPPORTED_STRUCTURAL_SPEC_VERSION = "track-b-structural-v2"
REQUIRED_TOP_LEVEL_FIELDS = (
    "freeze_version", "freeze_date", "warmup_data_start", "development_period",
    "validation_period", "final_holdout_period", "split_assignment", "symbol_universe",
    "data_source", "price_type", "timezone", "daily_bar_boundary", "status",
    "previous_freeze_version", "change_reason", "changed_fields",
)


class TrackBConfigError(ValueError):
    """Raised when the current Track B freeze artifact is invalid."""


@dataclass(frozen=True)
class StructuralValidationSummary:
    """Structural-validation identity bound to one canonical Track B dataset."""

    freeze_version: int
    structural_spec_version: str
    dataset_fingerprint: str
    dataset_fingerprint_algorithm: str
    status_by_symbol: Mapping[str, str]


@dataclass(frozen=True)
class PeriodRange:
    start: pd.Period
    end: pd.Period

    def contains(self, month: pd.Period) -> bool:
        return self.start <= month <= self.end


@dataclass(frozen=True)
class TrackBConfig:
    path: Path
    freeze_version: int
    freeze_date: str
    warmup_data_start: pd.Period
    development: PeriodRange
    validation: PeriodRange
    final_holdout: PeriodRange
    split_assignment_basis: str
    primary_symbols: tuple[str, ...]
    secondary_symbols: tuple[str, ...]
    data_source: str
    price_type: str
    timezone: str
    daily_boundary: Mapping[str, Any]
    status: str
    raw: Mapping[str, Any]

    @property
    def boundary_timezone(self) -> str:
        """Timezone used for calendar-month identity in the v2 contract."""
        return str(self.daily_boundary.get("calendar_month_timezone", "UTC"))

    @property
    def analysis_splits(self) -> tuple[str, str]:
        return ("development", "validation")

    def split_for_outcome(self, outcome_month: pd.Period) -> str:
        return self.split_for_holding_month(outcome_month)

    def split_for_holding_month(self, holding_month: pd.Period) -> str:
        """Assign the split by the month whose first Open owns the return."""
        if self.development.contains(holding_month):
            return "development"
        if self.validation.contains(holding_month):
            return "validation"
        if self.final_holdout.contains(holding_month):
            return "final_holdout"
        if holding_month < self.development.start:
            return "warmup"
        return "outside_frozen_period"


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TrackBConfigError(f"{name} must be a mapping")
    return value


def _period(value: Any, name: str) -> pd.Period:
    try:
        return pd.Period(str(value), freq="M")
    except Exception as exc:  # pragma: no cover - defensive error translation
        raise TrackBConfigError(f"{name} must be a YYYY-MM period") from exc


def _period_range(value: Any, name: str) -> PeriodRange:
    mapping = _mapping(value, name)
    if "start" not in mapping or "end" not in mapping:
        raise TrackBConfigError(f"{name} requires start and end")
    result = PeriodRange(_period(mapping["start"], f"{name}.start"), _period(mapping["end"], f"{name}.end"))
    if result.start > result.end:
        raise TrackBConfigError(f"{name}.start must not be after end")
    return result


def load_track_b_config(path: str | Path = "config/research_track_b.yaml") -> TrackBConfig:
    artifact_path = Path(path)
    if not artifact_path.exists():
        raise TrackBConfigError(f"Track B artifact does not exist: {artifact_path}")
    raw = yaml.safe_load(artifact_path.read_text(encoding="utf-8"))
    raw = _mapping(raw, "artifact")
    missing = [field for field in REQUIRED_TOP_LEVEL_FIELDS if field not in raw]
    if missing:
        raise TrackBConfigError(f"missing required fields: {missing}")

    version = raw["freeze_version"]
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        raise TrackBConfigError("freeze_version must be a positive integer")
    if raw["status"] != "frozen":
        raise TrackBConfigError("Track B artifact status must be frozen")
    previous_version = raw["previous_freeze_version"]
    if version == 1:
        if previous_version is not None:
            raise TrackBConfigError("freeze_version 1 must not have a previous freeze version")
    elif previous_version != version - 1:
        raise TrackBConfigError("previous_freeze_version must reference the immediately preceding version")
    if not str(raw["change_reason"]).strip():
        raise TrackBConfigError("change_reason must be non-empty")
    if not isinstance(raw["changed_fields"], (list, tuple)) or not raw["changed_fields"]:
        raise TrackBConfigError("changed_fields must be a non-empty list")

    split = _mapping(raw["split_assignment"], "split_assignment")
    basis = split.get("basis")
    if basis != "next_1m_return_outcome_month":
        raise TrackBConfigError("split_assignment.basis must be next_1m_return_outcome_month")
    if split.get("m2_basis", "holding_month") != "holding_month":
        raise TrackBConfigError("split_assignment.m2_basis must be holding_month")
    universe = _mapping(raw["symbol_universe"], "symbol_universe")
    primary = tuple(universe.get("primary", ()))
    secondary = tuple(universe.get("secondary_cross_robustness", ()))
    if not primary or not secondary or set(primary) & set(secondary):
        raise TrackBConfigError("primary and secondary symbol universes must be non-empty and disjoint")
    boundary = _mapping(raw["daily_bar_boundary"], "daily_bar_boundary")
    if "calendar_month_timezone" not in boundary:
        raise TrackBConfigError("daily_bar_boundary.calendar_month_timezone is required")
    if str(boundary["calendar_month_timezone"]) != "UTC":
        raise TrackBConfigError("Track B v2 calendar_month_timezone must be UTC")
    if boundary.get("ny17_conversion_required") is not False:
        raise TrackBConfigError("Track B v2 must not require NY17 timestamp conversion")
    for field in ("convention", "authority"):
        if field not in boundary:
            raise TrackBConfigError(f"daily_bar_boundary.{field} is required")

    result = TrackBConfig(
        path=artifact_path,
        freeze_version=version,
        freeze_date=str(raw["freeze_date"]),
        warmup_data_start=_period(raw["warmup_data_start"], "warmup_data_start"),
        development=_period_range(raw["development_period"], "development_period"),
        validation=_period_range(raw["validation_period"], "validation_period"),
        final_holdout=_period_range(raw["final_holdout_period"], "final_holdout_period"),
        split_assignment_basis=basis,
        primary_symbols=primary,
        secondary_symbols=secondary,
        data_source=str(raw["data_source"]),
        price_type=str(raw["price_type"]),
        timezone=str(raw["timezone"]),
        daily_boundary=dict(boundary),
        status=str(raw["status"]),
        raw=dict(raw),
    )
    if result.warmup_data_start > result.development.start:
        raise TrackBConfigError("warmup_data_start must not be after development start")
    if result.development.end >= result.validation.start or result.validation.end >= result.final_holdout.start:
        raise TrackBConfigError("evaluation periods must be non-overlapping and ordered")
    return result


def validate_m1a_real_data_gate(
    config: TrackBConfig,
    structural_status_by_symbol: Mapping[str, str],
    validation_freeze_version: int,
) -> tuple[str, ...]:
    """Validate the primary gate and return eligible secondary symbols."""
    if config.status != "frozen" or config.freeze_version <= 0:
        raise TrackBConfigError("current Track B artifact is not a valid frozen version")
    if validation_freeze_version != config.freeze_version:
        raise TrackBConfigError("structural validation freeze_version does not match current artifact")
    missing = [symbol for symbol in config.primary_symbols if symbol not in structural_status_by_symbol]
    if missing:
        raise TrackBConfigError(f"missing primary structural validation statuses: {missing}")
    invalid = {
        symbol: structural_status_by_symbol[symbol]
        for symbol in config.primary_symbols
        if structural_status_by_symbol[symbol] not in VALID_STRUCTURAL_STATUSES
    }
    if invalid:
        raise TrackBConfigError(f"primary structural validation gate failed: {invalid}")
    return tuple(
        symbol for symbol in config.secondary_symbols
        if structural_status_by_symbol.get(symbol) in VALID_STRUCTURAL_STATUSES
    )
