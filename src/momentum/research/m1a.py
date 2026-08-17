"""M1A Practical Predictability analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import statsmodels

from momentum.data.track_b import (
    MonthlyObservationResult,
    _build_synthetic_monthly_observations,
    _build_track_b_monthly_observations,
)
from momentum.research.inference import (
    CONFIDENCE_LEVEL,
    HAC_LAG,
    InferenceContractError,
    RankDeficientDesignError,
    SPEC_VERSION,
    _fit_statsmodels,
    coefficient_summary,
    linear_combination_summary,
    moving_block_bootstrap,
    outcome_months_are_consecutive,
    point_estimate,
)
from momentum.research.track_b_config import TrackBConfig


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
    universe_role: str,
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
            "two_way_clustered": "symbol x outcome_month",
        }.get(covariance_method),
        "data_source": config.data_source,
        "price_type": config.price_type,
        "timezone": config.timezone,
        "daily_boundary": config.daily_boundary["convention"],
        "spec_version": SPEC_VERSION,
        "freeze_version": config.freeze_version,
        "result_role": result_role,
        "universe_role": universe_role,
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
        if covariance_method == "calendar_month_clustered":
            groups = pd.factorize(frame["outcome_month"], sort=True)[0]
        if covariance_method == "two_way_clustered":
            groups = pd.factorize(frame["symbol"], sort=True)[0]
            second_groups = pd.factorize(frame["outcome_month"], sort=True)[0]
        fitted = _fit_statsmodels(
            y,
            x,
            covariance_method,
            groups=groups,
            second_groups=second_groups,
        )
        return fitted, fitted.params, None
    except InferenceContractError:
        return None, None, "cluster_df_mismatch"
    except RankDeficientDesignError:
        return None, None, "rank_deficient_design"
    except (np.linalg.LinAlgError, ValueError, TypeError, ZeroDivisionError) as exc:
        try:
            params = point_estimate(y, x)
        except (np.linalg.LinAlgError, ValueError, RankDeficientDesignError):
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
    universe_role: str = "primary",
) -> dict[str, Any]:
    if covariance_method == "HAC":
        inference_method = "OLS + HAC/Newey-West"
        lag_or_cluster = "hac_lag=12_months"
    elif covariance_method == "calendar_month_clustered":
        inference_method = "OLS + calendar-month clustered SE"
        lag_or_cluster = "cluster=outcome_month"
    else:
        inference_method = "OLS + two-way clustered SE"
        lag_or_cluster = "cluster=symbol x outcome_month"
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
        universe_role=universe_role,
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
        if covariance_method == "calendar_month_clustered":
            count = int(frame["outcome_month"].nunique())
            row.update({
                "outcome_month_cluster_count": count,
                "degrees_of_freedom_expected": count - 1,
                "statsmodels_df_resid_inference": None,
                "df_validation_status": "mismatch" if unavailable_reason == "cluster_df_mismatch" else "unavailable",
            })
        elif covariance_method == "two_way_clustered":
            symbol_count = int(frame["symbol"].nunique())
            month_count = int(frame["outcome_month"].nunique())
            row.update({
                "statsmodels_covariance_kwargs": {"use_correction": True},
                "project_inference_convention": {
                    "df_correction": True,
                    "use_t": True,
                    "degrees_of_freedom_rule": "min(symbol_cluster_count, outcome_month_cluster_count) - 1",
                },
                "symbol_cluster_count": symbol_count,
                "outcome_month_cluster_count": month_count,
                "degrees_of_freedom": min(symbol_count, month_count) - 1,
            })
    return row


def _sign_conditioned_rows(
    config: TrackBConfig,
    frame: pd.DataFrame,
    split: str,
    symbol: str,
    *,
    pooled: bool,
    result_role: str = "primary",
    universe_role: str = "primary",
) -> list[dict[str, Any]]:
    zero_count = int((frame["sign"] == 0).sum())
    nonzero = frame.loc[frame["sign"] != 0].copy()
    if not len(nonzero):
        reason = "no_nonzero_predictor_observations"
        fitted = None
        params = None
    else:
        nonzero["positive_indicator"] = (nonzero["sign"] > 0).astype("float64")
        covariance_method = "calendar_month_clustered" if pooled else "HAC"
        if nonzero["positive_indicator"].nunique() < 2:
            fitted, params, reason = None, None, "rank_deficient_design"
        else:
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
            result_role=result_role,
            universe_role=universe_role,
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
            if pooled:
                count = int(nonzero["outcome_month"].nunique())
                row.update({
                    "outcome_month_cluster_count": count,
                    "degrees_of_freedom_expected": count - 1,
                    "statsmodels_df_resid_inference": None,
                    "df_validation_status": "mismatch" if reason == "cluster_df_mismatch" else "unavailable",
                })
        row.update({"metric": metric, "regression_method": "OLS", **group_sizes})
        rows.append(row)
    return rows


def _bootstrap_row(config: TrackBConfig, frame: pd.DataFrame, split: str, analysis_name: str, predictor_column: str, predictor_definition: str) -> dict[str, Any]:
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
        universe_role="primary",
    )
    base_metadata = {
        "nobs": int(len(frame)),
        "regression_method": "OLS",
        "small_sample_correction": False,
        "bootstrap_method": "moving_block",
        "bootstrap_unit": "calendar_month",
        "block_length_months": 12,
        "bootstrap_replications": 5000,
        "bootstrap_seed": 20260817,
        "rng": "numpy.Generator(PCG64)",
        "confidence_level": CONFIDENCE_LEVEL,
        "interval_method": "percentile",
    }
    try:
        params = point_estimate(
            frame["next_1m_return"].to_numpy(dtype="float64"),
            frame[predictor_column].to_numpy(dtype="float64"),
        )
    except RankDeficientDesignError:
        row.update({
            **base_metadata,
            "alpha": float("nan"),
            "beta": float("nan"),
            "standard_error": float("nan"),
            "t_stat": float("nan"),
            "ci_lower": float("nan"),
            "ci_upper": float("nan"),
            "inference_status": "unavailable",
            "inference_unavailable_reason": "rank_deficient_design",
            "bootstrap_executed": False,
            "attempted_draws": 0,
            "successful_draws": 0,
            "failed_draws": 0,
            "skipped_draws": 5000,
        })
        return row
    period = getattr(config, split)
    try:
        bootstrap = moving_block_bootstrap(
            frame,
            predictor_column,
            "next_1m_return",
            period.start,
            period.end,
        )
    except ValueError as exc:
        row.update({
            **base_metadata,
            "alpha": float(params[0]),
            "beta": float(params[1]),
            "standard_error": float("nan"),
            "t_stat": float("nan"),
            "ci_lower": float("nan"),
            "ci_upper": float("nan"),
            "inference_status": "unavailable",
            "inference_unavailable_reason": f"bootstrap_error:{type(exc).__name__}",
            "bootstrap_executed": True,
            "attempted_draws": 5000,
            "successful_draws": 0,
            "failed_draws": 5000,
            "skipped_draws": 0,
        })
        return row
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


def _run_m1a_analysis(
    monthly_result: MonthlyObservationResult,
    config: TrackBConfig,
    *,
    data_origin: str,
    include_sensitivity: bool,
) -> M1AResult:
    """Run the statistical analysis on observations supplied by a gated builder."""
    observations = monthly_result.observations
    analysis_observations = observations[observations["split"].isin(config.analysis_splits)].copy()

    regression_rows: list[dict[str, Any]] = []
    sign_rows: list[dict[str, Any]] = []
    for split in config.analysis_splits:
        sample = analysis_observations[analysis_observations["split"] == split].copy()
        primary_sample = sample[sample["universe_role"] == "primary"].copy()
        secondary_sample = sample[sample["universe_role"] == "secondary_cross_robustness"].copy()
        if primary_sample.empty and secondary_sample.empty:
            continue
        for symbol, symbol_frame in primary_sample.groupby("symbol", sort=True):
            regression_rows.extend([
                _regression_row(
                    config, symbol_frame, split=split, symbol=str(symbol),
                    predictor_column="past_12m_return", analysis_name="continuous_regression",
                    predictor_definition="past_12m_return", covariance_method="HAC", symbol_level=True,
                    universe_role="primary",
                ),
                _regression_row(
                    config, symbol_frame, split=split, symbol=str(symbol),
                    predictor_column="sign", analysis_name="sign_predictor_regression",
                    predictor_definition="sign(past_12m_return), sign(0)=0", covariance_method="HAC", symbol_level=True,
                    universe_role="primary",
                ),
            ])
            sign_rows.extend(_sign_conditioned_rows(
                config, symbol_frame, split, str(symbol), pooled=False,
                result_role="primary", universe_role="primary",
            ))

        for symbol, symbol_frame in secondary_sample.groupby("symbol", sort=True):
            regression_rows.extend([
                _regression_row(
                    config, symbol_frame, split=split, symbol=str(symbol),
                    predictor_column="past_12m_return", analysis_name="continuous_regression",
                    predictor_definition="past_12m_return", covariance_method="HAC", symbol_level=True,
                    result_role="robustness", universe_role="secondary_cross_robustness",
                ),
                _regression_row(
                    config, symbol_frame, split=split, symbol=str(symbol),
                    predictor_column="sign", analysis_name="sign_predictor_regression",
                    predictor_definition="sign(past_12m_return), sign(0)=0", covariance_method="HAC", symbol_level=True,
                    result_role="robustness", universe_role="secondary_cross_robustness",
                ),
            ])
            sign_rows.extend(_sign_conditioned_rows(
                config, symbol_frame, split, str(symbol), pooled=False,
                result_role="robustness", universe_role="secondary_cross_robustness",
            ))

        if primary_sample.empty:
            continue
        regression_rows.extend([
            _regression_row(
                config, primary_sample, split=split, symbol="__pooled__",
                predictor_column="past_12m_return", analysis_name="continuous_regression",
                predictor_definition="past_12m_return", covariance_method="calendar_month_clustered", symbol_level=False,
                universe_role="primary",
            ),
            _regression_row(
                config, primary_sample, split=split, symbol="__pooled__",
                predictor_column="sign", analysis_name="sign_predictor_regression",
                predictor_definition="sign(past_12m_return), sign(0)=0", covariance_method="calendar_month_clustered", symbol_level=False,
                universe_role="primary",
            ),
        ])
        sign_rows.extend(_sign_conditioned_rows(
            config, primary_sample, split, "__pooled__", pooled=True,
            result_role="primary", universe_role="primary",
        ))

        if include_sensitivity:
            for predictor_column, analysis_name, definition in (
                ("past_12m_return", "continuous_regression", "past_12m_return"),
                ("sign", "sign_predictor_regression", "sign(past_12m_return), sign(0)=0"),
            ):
                regression_rows.append(_regression_row(
                    config, primary_sample, split=split, symbol="__pooled__",
                    predictor_column=predictor_column, analysis_name=analysis_name,
                    predictor_definition=definition, covariance_method="two_way_clustered", symbol_level=False,
                    result_role="sensitivity",
                    universe_role="primary",
                ))
                regression_rows.append(_bootstrap_row(
                    config, primary_sample, split, analysis_name, predictor_column, definition,
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


def run_m1a_track_b(
    daily: pd.DataFrame,
    config: TrackBConfig,
    structural_status_by_symbol: dict[str, str],
    validation_freeze_version: int,
    *,
    include_sensitivity: bool = True,
) -> M1AResult:
    """Run the production M1A Track B path with its internal structural gate."""
    monthly_result = _build_track_b_monthly_observations(
        daily,
        config,
        structural_status_by_symbol,
        validation_freeze_version,
    )
    return _run_m1a_analysis(
        monthly_result,
        config,
        data_origin="track_b",
        include_sensitivity=include_sensitivity,
    )


def _run_m1a_synthetic(
    daily: pd.DataFrame,
    config: TrackBConfig,
    *,
    include_sensitivity: bool = True,
) -> M1AResult:
    """Private test-support entry point; not part of the production API."""
    monthly_result = _build_synthetic_monthly_observations(daily, config)
    return _run_m1a_analysis(
        monthly_result,
        config,
        data_origin="synthetic",
        include_sensitivity=include_sensitivity,
    )
