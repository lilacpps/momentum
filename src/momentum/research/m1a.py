"""M1A Practical Predictability analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import statsmodels

from momentum.data.track_b import MonthlyObservationResult, build_monthly_observations
from momentum.research.inference import (
    CONFIDENCE_LEVEL,
    HAC_LAG,
    SPEC_VERSION,
    _fit_statsmodels,
    coefficient_summary,
    linear_combination_summary,
    moving_block_bootstrap,
    outcome_months_are_consecutive,
    point_estimate,
)
from momentum.research.track_b_config import TrackBConfig, validate_m1a_real_data_gate


@dataclass(frozen=True)
class M1AResult:
    observations: pd.DataFrame
    sign_conditioned_results: pd.DataFrame
    regression_results: pd.DataFrame
    diagnostics: dict[str, Any]
    metadata: dict[str, Any]


def _sample_period(config: TrackBConfig, split: str) -> str:
    period = getattr(config, split)
    return f"{period.start}/{period.end}"


def _common_metadata(
    config: TrackBConfig,
    *,
    analysis_name: str,
    symbol: str,
    split: str,
    predictor_definition: str,
    dependent_definition: str,
    inference_method: str,
    covariance_method: str,
    lag_or_cluster: str,
    result_role: str,
) -> dict[str, Any]:
    return {
        "track": "Track B",
        "workstream": "M1A Practical Predictability",
        "analysis_name": analysis_name,
        "symbol": symbol,
        "sample_period": _sample_period(config, split),
        "return_type": "calendar_month_close_to_close",
        "predictor_definition": predictor_definition,
        "dependent_definition": dependent_definition,
        "inference_method": inference_method,
        "covariance_method": covariance_method,
        "lag_or_cluster": lag_or_cluster,
        "hac_lag": HAC_LAG if covariance_method == "HAC" else None,
        "cluster_variable": {
            "calendar_month_clustered": "outcome_month",
            "two_way_clustered": "symbol × outcome_month",
        }.get(covariance_method),
        "data_source": config.data_source,
        "price_type": config.price_type,
        "timezone": config.timezone,
        "daily_boundary": config.daily_boundary["convention"],
        "spec_version": SPEC_VERSION,
        "freeze_version": config.freeze_version,
        "result_role": result_role,
        "library": "statsmodels",
        "library_version": statsmodels.__version__,
        "confidence_level": CONFIDENCE_LEVEL,
    }


def _fit_or_unavailable(
    frame: pd.DataFrame,
    predictor_column: str,
    *,
    covariance_method: str,
    symbol_level: bool,
) -> tuple[Any | None, np.ndarray | None, str | None]:
    x = frame[predictor_column].to_numpy(dtype="float64")
    y = frame["next_1m_return"].to_numpy(dtype="float64")
    if symbol_level and not outcome_months_are_consecutive(frame["outcome_month"]):
        try:
            return None, point_estimate(y, x), "non_consecutive_calendar_months"
        except (np.linalg.LinAlgError, ValueError):
            return None, None, "non_consecutive_calendar_months"
    try:
        groups = None
        second_groups = None
        if covariance_method in {"calendar_month_clustered", "two_way_clustered"}:
            groups = pd.factorize(frame["outcome_month"], sort=True)[0]
        if covariance_method == "two_way_clustered":
            second_groups = pd.factorize(frame["symbol"], sort=True)[0]
        fitted = _fit_statsmodels(
            y,
            x,
            covariance_method,
            groups=groups,
            second_groups=second_groups,
        )
        return fitted, fitted.params, None
    except (np.linalg.LinAlgError, ValueError, TypeError, ZeroDivisionError) as exc:
        try:
            params = point_estimate(y, x)
        except (np.linalg.LinAlgError, ValueError):
            params = None
        return None, params, f"inference_error:{type(exc).__name__}"


def _regression_row(
    config: TrackBConfig,
    frame: pd.DataFrame,
    *,
    split: str,
    symbol: str,
    predictor_column: str,
    analysis_name: str,
    predictor_definition: str,
    covariance_method: str,
    symbol_level: bool,
    result_role: str = "primary",
) -> dict[str, Any]:
    if covariance_method == "HAC":
        inference_method = "OLS + HAC/Newey-West"
        lag_or_cluster = "hac_lag=12_months"
    elif covariance_method == "calendar_month_clustered":
        inference_method = "OLS + calendar-month clustered SE"
        lag_or_cluster = "cluster=outcome_month"
    else:
        inference_method = "OLS + two-way clustered SE"
        lag_or_cluster = "cluster=symbol × outcome_month"
    row = _common_metadata(
        config,
        analysis_name=analysis_name,
        symbol=symbol,
        split=split,
        predictor_definition=predictor_definition,
        dependent_definition="next_1m_return",
        inference_method=inference_method,
        covariance_method=covariance_method,
        lag_or_cluster=lag_or_cluster,
        result_role=result_role,
    )
    fitted, params, unavailable_reason = _fit_or_unavailable(
        frame,
        predictor_column,
        covariance_method=covariance_method,
        symbol_level=symbol_level,
    )
    row.update({
        "alpha": float(params[0]) if params is not None else float("nan"),
        "beta": float(params[1]) if params is not None else float("nan"),
        "nobs": int(len(frame)),
        "inference_status": "available" if fitted is not None else "unavailable",
        "inference_unavailable_reason": unavailable_reason,
        "regression_method": "OLS",
        "small_sample_correction": True,
    })
    if fitted is not None:
        row.update(coefficient_summary(fitted))
        row.update(fitted.metadata)
    else:
        row.update({
            "standard_error": float("nan"),
            "t_stat": float("nan"),
            "ci_lower": float("nan"),
            "ci_upper": float("nan"),
            "covariance_options": {
                "kernel": "bartlett",
                "maxlags": HAC_LAG,
                "use_correction": True,
                "use_t": True,
            } if covariance_method == "HAC" else {
                "use_correction": True,
                "df_correction": True,
                "use_t": True,
            },
        })
    return row


def _sign_conditioned_rows(config: TrackBConfig, frame: pd.DataFrame, split: str, symbol: str, *, pooled: bool) -> list[dict[str, Any]]:
    zero_count = int((frame["sign"] == 0).sum())
    nonzero = frame.loc[frame["sign"] != 0].copy()
    if not len(nonzero):
        reason = "no_nonzero_predictor_observations"
        fitted = None
        params = None
    else:
        nonzero["positive_indicator"] = (nonzero["sign"] > 0).astype("float64")
        covariance_method = "calendar_month_clustered" if pooled else "HAC"
        fitted, params, reason = _fit_or_unavailable(
            nonzero,
            "positive_indicator",
            covariance_method=covariance_method,
            symbol_level=not pooled,
        )
    covariance_method = "calendar_month_clustered" if pooled else "HAC"
    group_sizes = {
        "positive_nobs": int((nonzero["sign"] > 0).sum()),
        "negative_nobs": int((nonzero["sign"] < 0).sum()),
        "zero_nobs": zero_count,
    }
    definitions = {
        "positive_mean": (1.0, 1.0),
        "negative_mean": (1.0, 0.0),
        "difference": (0.0, 1.0),
    }
    rows: list[dict[str, Any]] = []
    for metric, weights in definitions.items():
        row = _common_metadata(
            config,
            analysis_name="sign_conditioned_effect",
            symbol=symbol,
            split=split,
            predictor_definition="positive indicator on nonzero past_12m_return observations",
            dependent_definition="next_1m_return",
            inference_method="positive-indicator OLS + " + ("calendar-month clustered SE" if pooled else "HAC/Newey-West"),
            covariance_method=covariance_method,
            lag_or_cluster="cluster=outcome_month" if pooled else "hac_lag=12_months",
            result_role="primary",
        )
        if fitted is not None:
            summary = linear_combination_summary(fitted, weights)
            row.update(summary)
            row["inference_status"] = "available"
            row["inference_unavailable_reason"] = None
            row.update(fitted.metadata)
        else:
            estimate = float(weights[0] * params[0] + weights[1] * params[1]) if params is not None else float("nan")
            row.update({
                "estimate": estimate,
                "standard_error": float("nan"),
                "t_stat": float("nan"),
                "ci_lower": float("nan"),
                "ci_upper": float("nan"),
                "nobs": int(len(nonzero)),
                "inference_status": "unavailable",
                "inference_unavailable_reason": reason,
                "covariance_options": {
                    "kernel": "bartlett", "maxlags": HAC_LAG,
                    "use_correction": True, "use_t": True,
                } if not pooled else {
                    "use_correction": True, "df_correction": True, "use_t": True,
                },
            })
        row.update({"metric": metric, "regression_method": "OLS", **group_sizes})
        rows.append(row)
    return rows


def _bootstrap_row(config: TrackBConfig, frame: pd.DataFrame, split: str, analysis_name: str, predictor_column: str, predictor_definition: str) -> dict[str, Any]:
    params = point_estimate(
        frame["next_1m_return"].to_numpy(dtype="float64"),
        frame[predictor_column].to_numpy(dtype="float64"),
    )
    period = getattr(config, split)
    bootstrap = moving_block_bootstrap(
        frame,
        predictor_column,
        "next_1m_return",
        period.start,
        period.end,
    )
    row = _common_metadata(
        config,
        analysis_name=analysis_name,
        symbol="__pooled__",
        split=split,
        predictor_definition=predictor_definition,
        dependent_definition="next_1m_return",
        inference_method="OLS + moving block bootstrap",
        covariance_method="moving_block_bootstrap",
        lag_or_cluster="block_length=12_calendar_month_slots",
        result_role="sensitivity",
    )
    row.update({
        "alpha": float(params[0]),
        "beta": float(params[1]),
        "standard_error": bootstrap.standard_error,
        "t_stat": float(params[1] / bootstrap.standard_error) if bootstrap.standard_error > 0 else float("nan"),
        "ci_lower": bootstrap.ci_lower,
        "ci_upper": bootstrap.ci_upper,
        "nobs": int(len(frame)),
        "inference_status": "available",
        "inference_unavailable_reason": None,
        "regression_method": "OLS",
        "small_sample_correction": False,
        **bootstrap.metadata,
    })
    return row


def run_m1a(
    daily: pd.DataFrame,
    config: TrackBConfig,
    *,
    data_origin: str = "synthetic",
    structural_status_by_symbol: dict[str, str] | None = None,
    validation_freeze_version: int | None = None,
    include_sensitivity: bool = True,
) -> M1AResult:
    """Run M1A on supplied daily data without loading historical files."""
    if data_origin not in {"synthetic", "track_b"}:
        raise ValueError("data_origin must be synthetic or track_b")
    if data_origin == "track_b":
        if structural_status_by_symbol is None or validation_freeze_version is None:
            raise ValueError("track_b execution requires structural validation statuses and freeze version")
        eligible_secondary = validate_m1a_real_data_gate(
            config, structural_status_by_symbol, validation_freeze_version
        )
        requested_symbols = set(config.primary_symbols) | set(eligible_secondary)
        available_symbols = set(daily["symbol"].dropna().astype(str)) if "symbol" in daily else set()
        missing_primary = sorted(set(config.primary_symbols) - available_symbols)
        if missing_primary:
            raise ValueError(f"track_b input is missing frozen primary symbols: {missing_primary}")
    else:
        requested_symbols = set(daily["symbol"].dropna().astype(str)) if "symbol" in daily else set()

    monthly_result: MonthlyObservationResult = build_monthly_observations(daily, config)
    observations = monthly_result.observations
    if requested_symbols:
        observations = observations[observations["symbol"].astype(str).isin(requested_symbols)].copy()
    analysis_observations = observations[observations["split"].isin(config.analysis_splits)].copy()

    regression_rows: list[dict[str, Any]] = []
    sign_rows: list[dict[str, Any]] = []
    for split in config.analysis_splits:
        sample = analysis_observations[analysis_observations["split"] == split].copy()
        if sample.empty:
            continue
        for symbol, symbol_frame in sample.groupby("symbol", sort=True):
            regression_rows.extend([
                _regression_row(
                    config, symbol_frame, split=split, symbol=str(symbol),
                    predictor_column="past_12m_return", analysis_name="continuous_regression",
                    predictor_definition="past_12m_return", covariance_method="HAC", symbol_level=True,
                ),
                _regression_row(
                    config, symbol_frame, split=split, symbol=str(symbol),
                    predictor_column="sign", analysis_name="sign_predictor_regression",
                    predictor_definition="sign(past_12m_return), sign(0)=0", covariance_method="HAC", symbol_level=True,
                ),
            ])
            sign_rows.extend(_sign_conditioned_rows(config, symbol_frame, split, str(symbol), pooled=False))

        regression_rows.extend([
            _regression_row(
                config, sample, split=split, symbol="__pooled__",
                predictor_column="past_12m_return", analysis_name="continuous_regression",
                predictor_definition="past_12m_return", covariance_method="calendar_month_clustered", symbol_level=False,
            ),
            _regression_row(
                config, sample, split=split, symbol="__pooled__",
                predictor_column="sign", analysis_name="sign_predictor_regression",
                predictor_definition="sign(past_12m_return), sign(0)=0", covariance_method="calendar_month_clustered", symbol_level=False,
            ),
        ])
        sign_rows.extend(_sign_conditioned_rows(config, sample, split, "__pooled__", pooled=True))

        if include_sensitivity:
            for predictor_column, analysis_name, definition in (
                ("past_12m_return", "continuous_regression", "past_12m_return"),
                ("sign", "sign_predictor_regression", "sign(past_12m_return), sign(0)=0"),
            ):
                regression_rows.append(_regression_row(
                    config, sample, split=split, symbol="__pooled__",
                    predictor_column=predictor_column, analysis_name=analysis_name,
                    predictor_definition=definition, covariance_method="two_way_clustered", symbol_level=False,
                    result_role="sensitivity",
                ))
                regression_rows.append(_bootstrap_row(
                    config, sample, split, analysis_name, predictor_column, definition,
                ))

    diagnostics = dict(monthly_result.diagnostics)
    diagnostics["inference_unavailable_count"] = int(sum(
        row.get("inference_status") == "unavailable" for row in regression_rows + sign_rows
    ))
    diagnostics["data_origin"] = data_origin
    metadata = {
        "track": "Track B",
        "workstream": "M1A Practical Predictability",
        "spec_version": SPEC_VERSION,
        "freeze_version": config.freeze_version,
        "data_source": config.data_source,
        "price_type": config.price_type,
        "timezone": config.timezone,
        "daily_boundary": dict(config.daily_boundary),
        "data_origin": data_origin,
        "final_holdout_included": False,
    }
    return M1AResult(
        observations=analysis_observations.reset_index(drop=True),
        sign_conditioned_results=pd.DataFrame(sign_rows),
        regression_results=pd.DataFrame(regression_rows),
        diagnostics=diagnostics,
        metadata=metadata,
    )
