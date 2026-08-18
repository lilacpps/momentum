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
from datetime import datetime, time, timedelta
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
    session_close_month: str

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
        if self._boundary_ns is None or tick.timestamp_ns > self._boundary_ns:
            # The current session is closed by the first boundary at or after
            # the tick.  On a gap, recompute directly from this tick; do not
            # walk through or synthesize empty intermediate sessions.
            boundary = _session_boundary_utc(
                tick.timestamp,
                boundary_timezone=self.boundary_timezone,
                boundary_time=self.boundary_time,
            )
            boundary_ns = int(boundary.value)
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


def iter_exness_ticks(
    path: str | Path,
    *,
    symbol: str,
    source_file_order: int,
    chunksize: int = DEFAULT_CHUNKSIZE,
    diagnostics: dict[str, Any] | None = None,
    count_diagnostics: bool = True,
    boundary_timezone: str = BOUNDARY_TZ,
    boundary_time: time = BOUNDARY_TIME,
    status_months: frozenset[str] | None = None,
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
        row_offset = 0
        for chunk in reader:
            missing = [column for column in EXNESS_REQUIRED_COLUMNS if column not in chunk.columns]
            if missing:
                raise StructuralValidationError(
                    f"Exness CSV {path} is missing required columns: {missing}"
                )
            timestamp_text = chunk["Timestamp"].astype("string").str.strip()
            explicit_timezone = timestamp_text.str.match(
                r"^.*(?:[zZ]|[+-]\d{2}:?\d{2})$", na=False
            )
            # The explicit-timezone mask is applied before utc=True.  This
            # prevents pandas from interpreting naive strings as UTC.
            parsed_timestamps = pd.to_datetime(
                chunk["Timestamp"].where(explicit_timezone),
                errors="coerce",
                utc=True,
                format="mixed",
            )
            timestamp_valid = explicit_timezone & parsed_timestamps.notna()
            local_timestamps = parsed_timestamps.dt.tz_convert(boundary_timezone)
            after_boundary = (
                (local_timestamps.dt.hour > boundary_time.hour)
                | (
                    (local_timestamps.dt.hour == boundary_time.hour)
                    & (local_timestamps.dt.minute > boundary_time.minute)
                )
                | (
                    (local_timestamps.dt.hour == boundary_time.hour)
                    & (local_timestamps.dt.minute == boundary_time.minute)
                    & (local_timestamps.dt.second > boundary_time.second)
                )
                | (
                    (local_timestamps.dt.hour == boundary_time.hour)
                    & (local_timestamps.dt.minute == boundary_time.minute)
                    & (local_timestamps.dt.second == boundary_time.second)
                    & (local_timestamps.dt.microsecond > boundary_time.microsecond)
                )
            ).fillna(False)
            local_dates = pd.to_datetime(local_timestamps.dt.date)
            session_dates = local_dates + pd.to_timedelta(
                after_boundary.astype("int64"), unit="D"
            )
            session_close_months = session_dates.dt.to_period("M").astype("string")
            if status_months is None:
                status_timestamp = timestamp_valid
            else:
                status_timestamp = timestamp_valid & session_close_months.isin(status_months)
            bid_values = pd.to_numeric(chunk["Bid"], errors="coerce").to_numpy(
                dtype="float64", na_value=np.nan
            )
            bid_valid = pd.Series(
                np.isfinite(bid_values) & (bid_values > 0), index=chunk.index
            )
            source_symbols = chunk["Symbol"].astype("string")
            source_symbol_matches = source_symbols.eq(symbol).fillna(False)
            valid_timestamp_and_bid = timestamp_valid & bid_valid
            valid_rows = valid_timestamp_and_bid & source_symbol_matches

            if diagnostics is not None and count_diagnostics:
                diagnostics["timestamp_parse_errors"] += int((~timestamp_valid).sum())
                diagnostics["nonfinite_or_invalid_bid_rows"] += int(
                    (status_timestamp & ~bid_valid).sum()
                )
                diagnostics["source_symbol_mismatch_count"] += int(
                    (status_timestamp & bid_valid & ~source_symbol_matches).sum()
                )

            for local_position in np.flatnonzero(valid_rows.to_numpy()):
                position = int(local_position)
                yield _Tick(
                    parsed_timestamps.iloc[position],
                    float(bid_values[position]),
                    source_file_order,
                    row_offset + position,
                    str(session_close_months.iloc[position]),
                )
            row_offset += len(chunk)
    except pd.errors.ParserError as exc:
        raise StructuralValidationError(f"cannot parse Exness CSV {path}") from exc


def _session_boundary_utc(
    timestamp: pd.Timestamp,
    *,
    boundary_timezone: str = BOUNDARY_TZ,
    boundary_time: time = BOUNDARY_TIME,
) -> pd.Timestamp:
    """Return the first NY boundary at or after an explicit UTC timestamp."""
    boundary_zone = ZoneInfo(boundary_timezone)
    local = timestamp.tz_convert(boundary_timezone)
    local_date = local.date()
    candidate = pd.Timestamp(datetime.combine(local_date, boundary_time, tzinfo=boundary_zone))
    candidate = candidate.tz_convert("UTC")
    if timestamp <= candidate:
        return candidate
    next_date = local_date + timedelta(days=1)
    next_boundary = pd.Timestamp(datetime.combine(next_date, boundary_time, tzinfo=boundary_zone))
    return next_boundary.tz_convert("UTC")


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
    boundary_timezone: str,
    boundary_time: time,
    status_months: frozenset[str] | None,
) -> Iterator[_Tick]:
    for source_file_order, path in enumerate(files):
        yield from iter_exness_ticks(
            path,
            symbol=symbol,
            source_file_order=source_file_order,
            chunksize=chunksize,
            diagnostics=diagnostics,
            count_diagnostics=count_diagnostics,
            boundary_timezone=boundary_timezone,
            boundary_time=boundary_time,
            status_months=status_months,
        )


def _canonical_unique_ticks(
    ticks: Iterator[_Tick],
    diagnostics: dict[str, Any],
    builder: _DailyBuilder,
    *,
    track_order: bool,
    status_months: frozenset[str],
) -> None:
    previous_timestamp_ns: int | None = None
    requested_previous_timestamp_ns: int | None = None
    timestamp_seen_bids: set[float] = set()
    for tick in ticks:
        timestamp_ns = tick.timestamp_ns
        in_requested_range = tick.session_close_month in status_months
        if diagnostics["first_valid_tick"] is None:
            diagnostics["first_valid_tick"] = tick.timestamp
        diagnostics["last_valid_tick"] = tick.timestamp
        if not in_requested_range:
            continue
        if in_requested_range:
            if (
                track_order
                and requested_previous_timestamp_ns is not None
                and timestamp_ns < requested_previous_timestamp_ns
            ):
                diagnostics["out_of_order_detected"] = True
            if requested_previous_timestamp_ns == timestamp_ns:
                diagnostics["repeated_timestamp_count"] += 1
            requested_previous_timestamp_ns = timestamp_ns
        if previous_timestamp_ns != timestamp_ns:
            timestamp_seen_bids = set()
        previous_timestamp_ns = timestamp_ns
        if tick.bid in timestamp_seen_bids:
            if in_requested_range:
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
    status_months: frozenset[str],
) -> pd.DataFrame:
    """Re-read one out-of-order symbol through a disk-backed SQLite cursor."""
    with tempfile.TemporaryDirectory(prefix="momentum-track-b-") as temp_dir:
        database_path = Path(temp_dir) / "ticks.sqlite3"
        connection = sqlite3.connect(database_path)
        try:
            connection.execute(
                "CREATE TABLE ticks (timestamp_ns INTEGER NOT NULL, bid REAL NOT NULL, "
                "source_file_order INTEGER NOT NULL, source_row_number INTEGER NOT NULL, "
                "session_close_month TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX ticks_canonical_order ON ticks "
                "(timestamp_ns, source_file_order, source_row_number)"
            )
            batch: list[tuple[int, float, int, int, str]] = []
            for tick in _source_ticks(
                files,
                symbol,
                chunksize=chunksize,
                diagnostics=diagnostics,
                count_diagnostics=False,
                boundary_timezone=boundary_timezone,
                boundary_time=boundary_time,
                status_months=status_months,
            ):
                batch.append((
                    tick.timestamp_ns,
                    tick.bid,
                    tick.source_file_order,
                    tick.source_row_number,
                    tick.session_close_month,
                ))
                if len(batch) >= 10_000:
                    connection.executemany("INSERT INTO ticks VALUES (?, ?, ?, ?, ?)", batch)
                    batch.clear()
            if batch:
                connection.executemany("INSERT INTO ticks VALUES (?, ?, ?, ?, ?)", batch)
            connection.commit()

            sorted_ticks = (
                _Tick(
                    pd.Timestamp(timestamp_ns, unit="ns", tz="UTC"),
                    float(bid),
                    int(source_file_order),
                    int(source_row_number),
                    str(session_close_month),
                )
                for timestamp_ns, bid, source_file_order, source_row_number, session_close_month
                in connection.execute(
                "SELECT timestamp_ns, bid, source_file_order, source_row_number "
                ", session_close_month FROM ticks "
                "ORDER BY timestamp_ns, source_file_order, source_row_number"
                )
            )
            builder = _DailyBuilder(symbol, boundary_timezone, boundary_time)
            _canonical_unique_ticks(
                sorted_ticks,
                diagnostics,
                builder,
                track_order=False,
                status_months=status_months,
            )
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
    status_months = frozenset(diagnostics["missing_calendar_months"] + diagnostics["available_calendar_months"])
    if not status_months:
        status_months = frozenset(
            str(month)
            for month in pd.period_range(config.warmup_data_start, config.final_holdout.end, freq="M")
        )
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
                boundary_timezone=config.boundary_timezone,
                boundary_time=boundary_time,
                status_months=status_months,
            ),
            diagnostics,
            builder,
            track_order=True,
            status_months=status_months,
        )
        if diagnostics["out_of_order_detected"]:
            # Discard all partial state. The full symbol is rebuilt from source.
            # Fallback diagnostics must preserve first-pass invalid-row counts
            # and use only its own canonical duplicate counts.
            fallback_diagnostics = {
                **diagnostics,
                "first_valid_tick": None,
                "last_valid_tick": None,
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
                status_months=status_months,
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

    daily = _filter_daily_to_requested_range(daily, config)
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


def _filter_daily_to_requested_range(
    daily: pd.DataFrame,
    config: TrackBConfig,
) -> pd.DataFrame:
    """Keep only Daily rows whose local close month is requested/frozen."""
    if daily.empty:
        return daily.reset_index(drop=True)
    local_dates = daily["timestamp"].dt.tz_convert(config.boundary_timezone).dt.date
    local_months = pd.to_datetime(local_dates).dt.to_period("M")
    selected = local_months.between(
        config.warmup_data_start,
        config.final_holdout.end,
    )
    return daily.loc[selected].reset_index(drop=True)


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
    daily = _filter_daily_to_requested_range(daily, config)
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
