"""Production Track B raw-tick structural validation.

This module deliberately stops at canonical Daily OHLC construction.  It does
not calculate returns, predictors, regressions, PnL, Sharpe, or strategy
results.

The Exness adapter is based on the locally inspected converted CSV schema:
``Exness, Symbol, Timestamp, Bid, Ask``.  The inspected timestamps use an
explicit UTC ``Z`` suffix.  The adapter requires an explicit timezone on every
timestamp rather than localising naive values implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import math
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Iterator, Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from momentum.data.track_b import (
    REQUIRED_LONG_DAILY_COLUMNS,
    TrackBDailyValidationError,
    compute_track_b_daily_fingerprint,
    validate_track_b_daily,
)
from momentum.research.track_b_config import (
    SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
    SUPPORTED_STRUCTURAL_SPEC_VERSION,
    StructuralValidationSummary,
    TrackBConfig,
    load_track_b_config,
)

DEFAULT_DATA_ROOT = Path("data/raw")
DEFAULT_CHUNKSIZE = 100_000
BOUNDARY_TIME = time(17, 0)
BOUNDARY_TZ = "America/New_York"
EXNESS_REQUIRED_COLUMNS = ("Exness", "Symbol", "Timestamp", "Bid", "Ask")
DIAGNOSTIC_COLUMNS = (
    "symbol",
    "freeze_version",
    "structural_spec_version",
    "requested_start",
    "requested_end",
    "first_valid_tick",
    "last_valid_tick",
    "timestamp_parse_errors",
    "nonfinite_or_invalid_bid_rows",
    "out_of_order_detected",
    "repeated_timestamp_count",
    "exact_duplicate_row_count",
    "suspicious_gap_count",
    "daily_bar_count",
    "available_calendar_months",
    "missing_calendar_months",
    "validation_status",
    "warnings",
    "failure_reasons",
)


class StructuralValidationError(ValueError):
    """Raised for a programming or configuration error in the validator."""


@dataclass(frozen=True)
class StructuralValidationResult:
    """Canonical Daily data, symbol diagnostics, and M1A-compatible identity."""

    daily_ohlc: pd.DataFrame
    symbol_diagnostics: pd.DataFrame
    summary: StructuralValidationSummary


@dataclass(frozen=True)
class _Tick:
    timestamp: pd.Timestamp
    bid: float
    source_file_order: int
    source_row_number: int

    @property
    def timestamp_ns(self) -> int:
        return int(self.timestamp.value)


class _DailyBuilder:
    """Incrementally aggregate one symbol's canonical tick stream."""

    def __init__(self, symbol: str, boundary_timezone: str, boundary_time: time) -> None:
        self.symbol = symbol
        self.boundary_timezone = boundary_timezone
        self.boundary_time = boundary_time
        self._boundary_ns: int | None = None
        self._open: float | None = None
        self._high: float | None = None
        self._low: float | None = None
        self._close: float | None = None
        self.rows: list[dict[str, Any]] = []

    def add(self, tick: _Tick) -> None:
        boundary = _session_boundary_utc(
            tick.timestamp,
            boundary_timezone=self.boundary_timezone,
            boundary_time=self.boundary_time,
        )
        boundary_ns = int(boundary.value)
        if self._boundary_ns != boundary_ns:
            self._emit()
            self._boundary_ns = boundary_ns
            self._open = tick.bid
            self._high = tick.bid
            self._low = tick.bid
            self._close = tick.bid
            return

        assert self._high is not None
        assert self._low is not None
        self._high = max(self._high, tick.bid)
        self._low = min(self._low, tick.bid)
        self._close = tick.bid

    def finish(self) -> pd.DataFrame:
        self._emit()
        return _daily_frame(self.rows)

    def _emit(self) -> None:
        if self._boundary_ns is None:
            return
        assert self._open is not None
        assert self._high is not None
        assert self._low is not None
        assert self._close is not None
        self.rows.append({
            "symbol": self.symbol,
            "timestamp": pd.Timestamp(self._boundary_ns, unit="ns", tz="UTC"),
            "open": self._open,
            "high": self._high,
            "low": self._low,
            "close": self._close,
        })


def _daily_frame(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame({
            "symbol": pd.Series(dtype="string"),
            "timestamp": pd.Series(dtype="datetime64[ns, UTC]"),
            "open": pd.Series(dtype="float64"),
            "high": pd.Series(dtype="float64"),
            "low": pd.Series(dtype="float64"),
            "close": pd.Series(dtype="float64"),
        }, columns=REQUIRED_LONG_DAILY_COLUMNS)
    frame = pd.DataFrame(rows, columns=REQUIRED_LONG_DAILY_COLUMNS)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame.sort_values(["symbol", "timestamp"], kind="mergesort").reset_index(drop=True)


def _normalised_relative_path(path: Path, root: Path) -> str:
    """Return the cross-platform lexical source-manifest path."""
    return path.relative_to(root).as_posix()


def discover_track_b_source_files(data_root: str | Path, symbol: str) -> tuple[Path, ...]:
    """Discover direct-child CSV sources in deterministic normalized order."""
    root = Path(data_root)
    symbol_dir = root / symbol
    if not symbol_dir.is_dir():
        return ()
    files = [
        path for path in symbol_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".csv"
    ]
    return tuple(sorted(files, key=lambda path: _normalised_relative_path(path, root)))


def _parse_explicit_timestamp(value: Any) -> pd.Timestamp | None:
    if value is None or pd.isna(value):
        return None
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if pd.isna(timestamp) or timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return None
    try:
        return timestamp.tz_convert("UTC")
    except (TypeError, ValueError, OverflowError):
        return None


def _parse_positive_bid(value: Any) -> float | None:
    try:
        bid = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(bid) or bid <= 0:
        return None
    return bid


def iter_exness_ticks(
    path: str | Path,
    *,
    symbol: str,
    source_file_order: int,
    chunksize: int = DEFAULT_CHUNKSIZE,
    diagnostics: dict[str, Any] | None = None,
    count_diagnostics: bool = True,
) -> Iterator[_Tick]:
    """Yield valid ticks from one inspected Exness CSV without full loading."""
    if chunksize <= 0:
        raise StructuralValidationError("chunksize must be positive")
    path = Path(path)
    try:
        reader = pd.read_csv(
            path,
            chunksize=chunksize,
            dtype=object,
            keep_default_na=True,
        )
        first_chunk = True
        row_offset = 0
        for chunk in reader:
            missing = [column for column in EXNESS_REQUIRED_COLUMNS if column not in chunk.columns]
            if missing:
                raise StructuralValidationError(
                    f"Exness CSV {path} is missing required columns: {missing}"
                )
            if first_chunk:
                first_chunk = False
            for local_position, values in enumerate(chunk.itertuples(index=False, name=None)):
                row = dict(zip(chunk.columns, values))
                row_number = row_offset + local_position
                timestamp = _parse_explicit_timestamp(row.get("Timestamp"))
                if timestamp is None:
                    if diagnostics is not None and count_diagnostics:
                        diagnostics["timestamp_parse_errors"] += 1
                    continue
                bid = _parse_positive_bid(row.get("Bid"))
                if bid is None:
                    if diagnostics is not None and count_diagnostics:
                        diagnostics["nonfinite_or_invalid_bid_rows"] += 1
                    continue
                source_symbol = row.get("Symbol")
                if source_symbol is None or str(source_symbol) != symbol:
                    if diagnostics is not None and count_diagnostics:
                        diagnostics["source_symbol_mismatch_count"] += 1
                    continue
                yield _Tick(timestamp, bid, source_file_order, row_number)
            row_offset += len(chunk)
    except pd.errors.ParserError as exc:
        raise StructuralValidationError(f"cannot parse Exness CSV {path}") from exc


def _session_boundary_utc(
    timestamp: pd.Timestamp,
    *,
    boundary_timezone: str = BOUNDARY_TZ,
    boundary_time: time = BOUNDARY_TIME,
) -> pd.Timestamp:
    """Return the current NY 17:00 boundary for an explicit UTC timestamp."""
    boundary_zone = ZoneInfo(boundary_timezone)
    local = timestamp.tz_convert(boundary_timezone)
    local_date = local.date()
    candidate = pd.Timestamp(datetime.combine(local_date, boundary_time, tzinfo=boundary_zone))
    candidate = candidate.tz_convert("UTC")
    if timestamp < candidate:
        previous = local_date - timedelta(days=1)
        candidate = pd.Timestamp(datetime.combine(previous, boundary_time, tzinfo=boundary_zone))
        candidate = candidate.tz_convert("UTC")
    return candidate


def _new_diagnostics(symbol: str, config: TrackBConfig) -> dict[str, Any]:
    requested_months = [
        str(month)
        for month in pd.period_range(config.warmup_data_start, config.final_holdout.end, freq="M")
    ]
    return {
        "symbol": symbol,
        "freeze_version": config.freeze_version,
        "structural_spec_version": SUPPORTED_STRUCTURAL_SPEC_VERSION,
        "requested_start": str(config.warmup_data_start),
        "requested_end": str(config.final_holdout.end),
        "first_valid_tick": None,
        "last_valid_tick": None,
        "timestamp_parse_errors": 0,
        "nonfinite_or_invalid_bid_rows": 0,
        "out_of_order_detected": False,
        "repeated_timestamp_count": 0,
        "exact_duplicate_row_count": 0,
        "suspicious_gap_count": 0,
        "daily_bar_count": 0,
        "available_calendar_months": [],
        "missing_calendar_months": requested_months,
        "validation_status": "fail",
        "warnings": [],
        "failure_reasons": [],
        "source_symbol_mismatch_count": 0,
    }


def _source_ticks(
    files: Sequence[Path],
    symbol: str,
    *,
    chunksize: int,
    diagnostics: dict[str, Any],
    count_diagnostics: bool,
) -> Iterator[_Tick]:
    for source_file_order, path in enumerate(files):
        yield from iter_exness_ticks(
            path,
            symbol=symbol,
            source_file_order=source_file_order,
            chunksize=chunksize,
            diagnostics=diagnostics,
            count_diagnostics=count_diagnostics,
        )


def _canonical_unique_ticks(
    ticks: Iterator[_Tick],
    diagnostics: dict[str, Any],
    builder: _DailyBuilder,
    *,
    track_order: bool,
) -> None:
    previous_timestamp_ns: int | None = None
    timestamp_seen_bids: set[float] = set()
    for tick in ticks:
        timestamp_ns = tick.timestamp_ns
        if diagnostics["first_valid_tick"] is None:
            diagnostics["first_valid_tick"] = tick.timestamp
        diagnostics["last_valid_tick"] = tick.timestamp
        if track_order and previous_timestamp_ns is not None and timestamp_ns < previous_timestamp_ns:
            diagnostics["out_of_order_detected"] = True
        if previous_timestamp_ns != timestamp_ns:
            timestamp_seen_bids = set()
        else:
            diagnostics["repeated_timestamp_count"] += 1
        previous_timestamp_ns = timestamp_ns
        if tick.bid in timestamp_seen_bids:
            diagnostics["exact_duplicate_row_count"] += 1
            continue
        timestamp_seen_bids.add(tick.bid)
        builder.add(tick)


def _sqlite_fallback(
    files: Sequence[Path],
    symbol: str,
    *,
    chunksize: int,
    diagnostics: dict[str, Any],
    boundary_timezone: str,
    boundary_time: time,
) -> pd.DataFrame:
    """Re-read one out-of-order symbol through a disk-backed SQLite cursor."""
    with tempfile.TemporaryDirectory(prefix="momentum-track-b-") as temp_dir:
        database_path = Path(temp_dir) / "ticks.sqlite3"
        connection = sqlite3.connect(database_path)
        try:
            connection.execute(
                "CREATE TABLE ticks (timestamp_ns INTEGER NOT NULL, bid REAL NOT NULL, "
                "source_file_order INTEGER NOT NULL, source_row_number INTEGER NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX ticks_canonical_order ON ticks "
                "(timestamp_ns, source_file_order, source_row_number)"
            )
            batch: list[tuple[int, float, int, int]] = []
            for tick in _source_ticks(
                files,
                symbol,
                chunksize=chunksize,
                diagnostics=diagnostics,
                count_diagnostics=False,
            ):
                batch.append((tick.timestamp_ns, tick.bid, tick.source_file_order, tick.source_row_number))
                if len(batch) >= 10_000:
                    connection.executemany("INSERT INTO ticks VALUES (?, ?, ?, ?)", batch)
                    batch.clear()
            if batch:
                connection.executemany("INSERT INTO ticks VALUES (?, ?, ?, ?)", batch)
            connection.commit()

            builder = _DailyBuilder(symbol, boundary_timezone, boundary_time)
            previous_timestamp_ns: int | None = None
            timestamp_seen_bids: set[float] = set()
            for timestamp_ns, bid, source_file_order, source_row_number in connection.execute(
                "SELECT timestamp_ns, bid, source_file_order, source_row_number "
                "FROM ticks ORDER BY timestamp_ns, source_file_order, source_row_number"
            ):
                if diagnostics["first_valid_tick"] is None:
                    diagnostics["first_valid_tick"] = pd.Timestamp(timestamp_ns, unit="ns", tz="UTC")
                diagnostics["last_valid_tick"] = pd.Timestamp(timestamp_ns, unit="ns", tz="UTC")
                if previous_timestamp_ns != timestamp_ns:
                    timestamp_seen_bids = set()
                else:
                    diagnostics["repeated_timestamp_count"] += 1
                previous_timestamp_ns = timestamp_ns
                bid = float(bid)
                if bid in timestamp_seen_bids:
                    diagnostics["exact_duplicate_row_count"] += 1
                    continue
                timestamp_seen_bids.add(bid)
                builder.add(_Tick(
                    pd.Timestamp(timestamp_ns, unit="ns", tz="UTC"),
                    bid,
                    int(source_file_order),
                    int(source_row_number),
                ))
            return builder.finish()
        finally:
            connection.close()


def _process_symbol(
    symbol: str,
    files: Sequence[Path],
    config: TrackBConfig,
    *,
    chunksize: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    diagnostics = _new_diagnostics(symbol, config)
    boundary_time = _configured_boundary_time(config)
    if not files:
        diagnostics["failure_reasons"].append("missing_source_files")
        return _daily_frame(()), diagnostics

    try:
        builder = _DailyBuilder(symbol, config.boundary_timezone, boundary_time)
        _canonical_unique_ticks(
            _source_ticks(
                files,
                symbol,
                chunksize=chunksize,
                diagnostics=diagnostics,
                count_diagnostics=True,
            ),
            diagnostics,
            builder,
            track_order=True,
        )
        if diagnostics["out_of_order_detected"]:
            # Discard all partial state. The full symbol is rebuilt from source.
            # Fallback diagnostics must preserve first-pass invalid-row counts
            # and use only its own canonical duplicate counts.
            fallback_diagnostics = {
                **diagnostics,
                "repeated_timestamp_count": 0,
                "exact_duplicate_row_count": 0,
            }
            daily = _sqlite_fallback(
                files,
                symbol,
                chunksize=chunksize,
                diagnostics=fallback_diagnostics,
                boundary_timezone=config.boundary_timezone,
                boundary_time=boundary_time,
            )
            diagnostics["first_valid_tick"] = fallback_diagnostics["first_valid_tick"]
            diagnostics["last_valid_tick"] = fallback_diagnostics["last_valid_tick"]
            diagnostics["repeated_timestamp_count"] = fallback_diagnostics["repeated_timestamp_count"]
            diagnostics["exact_duplicate_row_count"] = fallback_diagnostics["exact_duplicate_row_count"]
        else:
            daily = builder.finish()
    except (OSError, StructuralValidationError, UnicodeError) as exc:
        diagnostics["failure_reasons"].append("source_corruption")
        diagnostics["failure_detail"] = str(exc)
        return _daily_frame(()), diagnostics

    diagnostics["daily_bar_count"] = len(daily)
    try:
        _validate_daily_invariants(daily)
    except StructuralValidationError:
        diagnostics["failure_reasons"].append("daily_ohlc_invariant_violation")
        return _daily_frame(()), diagnostics
    available, missing = _calendar_coverage(daily, config)
    diagnostics["available_calendar_months"] = available
    diagnostics["missing_calendar_months"] = missing
    diagnostics["suspicious_gap_count"] = _suspicious_gap_count(
        daily, boundary_timezone=config.boundary_timezone
    )
    if missing:
        diagnostics["failure_reasons"].append("missing_calendar_months")
    if len(daily) == 0:
        diagnostics["failure_reasons"].append("no_usable_bid_series")
    if diagnostics["source_symbol_mismatch_count"]:
        diagnostics["failure_reasons"].append("source_symbol_mismatch")

    warnings = diagnostics["warnings"]
    if diagnostics["out_of_order_detected"]:
        warnings.append("out_of_order_detected")
    if diagnostics["timestamp_parse_errors"] or diagnostics["nonfinite_or_invalid_bid_rows"]:
        warnings.append("invalid_rows_removed")
    if diagnostics["repeated_timestamp_count"]:
        warnings.append("repeated_timestamp")
    if diagnostics["exact_duplicate_row_count"]:
        warnings.append("exact_duplicate_removed")
    if diagnostics["suspicious_gap_count"]:
        warnings.append("suspicious_gap")
    diagnostics["validation_status"] = "fail" if diagnostics["failure_reasons"] else (
        "pass_with_warning" if warnings else "pass"
    )
    return daily, diagnostics


def _validate_daily_invariants(daily: pd.DataFrame) -> None:
    if daily.empty:
        return
    for column in ("open", "high", "low", "close"):
        values = daily[column].to_numpy(dtype="float64")
        if not np.isfinite(values).all() or (values <= 0).any():
            raise StructuralValidationError("daily_ohlc_invariant_violation")
    if not (
        (daily["high"] >= daily["open"]).all()
        and (daily["high"] >= daily["close"]).all()
        and (daily["low"] <= daily["open"]).all()
        and (daily["low"] <= daily["close"]).all()
        and (daily["high"] >= daily["low"]).all()
    ):
        raise StructuralValidationError("daily_ohlc_invariant_violation")


def _configured_boundary_time(config: TrackBConfig) -> time:
    try:
        return datetime.strptime(
            str(config.daily_boundary["boundary_local_time"]), "%H:%M"
        ).time()
    except (KeyError, TypeError, ValueError) as exc:
        raise StructuralValidationError("invalid daily boundary local time") from exc


def _calendar_coverage(daily: pd.DataFrame, config: TrackBConfig) -> tuple[list[str], list[str]]:
    requested = pd.period_range(config.warmup_data_start, config.final_holdout.end, freq="M")
    if daily.empty:
        return [], [str(month) for month in requested]
    local_dates = daily["timestamp"].dt.tz_convert(config.boundary_timezone).dt.date
    local_months = set(pd.to_datetime(local_dates).dt.to_period("M").astype(str))
    available = [str(month) for month in requested if str(month) in local_months]
    missing = [str(month) for month in requested if str(month) not in local_months]
    return available, missing


def _suspicious_gap_count(daily: pd.DataFrame, *, boundary_timezone: str) -> int:
    if len(daily) < 2:
        return 0
    timestamps = daily["timestamp"].sort_values().tolist()
    episodes = 0
    for previous, current in zip(timestamps, timestamps[1:]):
        previous_date = previous.tz_convert(boundary_timezone).date()
        current_date = current.tz_convert(boundary_timezone).date()
        missing_active_boundaries = 0
        cursor = previous_date + timedelta(days=1)
        while cursor < current_date:
            # Saturday is the only omitted boundary in the normal Friday->Sunday closure.
            if cursor.weekday() != 5:
                missing_active_boundaries += 1
            cursor += timedelta(days=1)
        if missing_active_boundaries >= 2:
            episodes += 1
    return episodes


def _finalize_diagnostics(frame: pd.DataFrame) -> pd.DataFrame:
    for column in DIAGNOSTIC_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    return frame.loc[:, DIAGNOSTIC_COLUMNS]


def run_track_b_structural_validation(
    data_root: str | Path = DEFAULT_DATA_ROOT,
    config_path: str | Path = "config/research_track_b.yaml",
    *,
    chunksize: int = DEFAULT_CHUNKSIZE,
) -> StructuralValidationResult:
    """Run Track B structural validation for every frozen symbol.

    The function performs source discovery and raw structural validation only.
    It does not invoke M1A or any return/performance calculation.
    """
    if chunksize <= 0:
        raise StructuralValidationError("chunksize must be positive")
    config = load_track_b_config(config_path)
    root = Path(data_root)
    symbols = config.primary_symbols + config.secondary_symbols
    daily_frames: list[pd.DataFrame] = []
    diagnostics: list[dict[str, Any]] = []
    for symbol in symbols:
        symbol_dir = root / symbol
        files = discover_track_b_source_files(root, symbol)
        if not symbol_dir.is_dir():
            item = _new_diagnostics(symbol, config)
            item["failure_reasons"].append("missing_source_directory")
            diagnostics.append(item)
            continue
        daily, item = _process_symbol(symbol, files, config, chunksize=chunksize)
        diagnostics.append(item)
        if not daily.empty:
            daily_frames.append(daily)

    daily = _daily_frame(
        pd.concat(daily_frames, ignore_index=True).to_dict("records")
        if daily_frames else ()
    )
    try:
        _validate_daily_invariants(daily)
        daily = validate_track_b_daily(daily, config)
    except (StructuralValidationError, TrackBDailyValidationError):
        for item in diagnostics:
            if item["daily_bar_count"]:
                item["validation_status"] = "fail"
                item["failure_reasons"].append("daily_validation_failed")
                item["warnings"] = list(dict.fromkeys(item["warnings"]))
        daily = _daily_frame(())
        daily = validate_track_b_daily(daily, config)

    fingerprint = compute_track_b_daily_fingerprint(daily)
    status_by_symbol = {
        str(item["symbol"]): str(item["validation_status"])
        for item in diagnostics
    }
    summary = StructuralValidationSummary(
        freeze_version=config.freeze_version,
        structural_spec_version=SUPPORTED_STRUCTURAL_SPEC_VERSION,
        dataset_fingerprint=fingerprint,
        dataset_fingerprint_algorithm=SUPPORTED_DATASET_FINGERPRINT_ALGORITHM,
        status_by_symbol=status_by_symbol,
    )
    diagnostics_frame = _finalize_diagnostics(pd.DataFrame(diagnostics))
    return StructuralValidationResult(daily, diagnostics_frame, summary)


__all__ = [
    "DEFAULT_CHUNKSIZE",
    "EXNESS_REQUIRED_COLUMNS",
    "StructuralValidationError",
    "StructuralValidationResult",
    "discover_track_b_source_files",
    "iter_exness_ticks",
    "run_track_b_structural_validation",
]
