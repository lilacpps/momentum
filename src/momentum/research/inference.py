"""Statsmodels-backed M1A inference helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.sandwich_covariance import cov_cluster_2groups

SPEC_VERSION = "m1a-practical-v1"
CONFIDENCE_LEVEL = 0.95
HAC_LAG = 12
HAC_OPTIONS = {
    "kernel": "bartlett",
    "maxlags": HAC_LAG,
    "use_correction": True,
    "use_t": True,
}
CLUSTER_OPTIONS = {
    "use_correction": True,
    "df_correction": True,
    "use_t": True,
}


@dataclass(frozen=True)
class FittedInference:
    params: np.ndarray
    covariance: np.ndarray
    degrees_of_freedom: float
    nobs: int
    metadata: dict[str, Any]


@dataclass(frozen=True)
class BootstrapSummary:
    standard_error: float
    ci_lower: float
    ci_upper: float
    successful_draws: int
    failed_draws: int
    metadata: dict[str, Any]


def point_estimate(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Return the unadjusted OLS intercept and slope."""
    design = sm.add_constant(np.asarray(x, dtype="float64"), has_constant="add")
    response = np.asarray(y, dtype="float64")
    fitted = sm.OLS(response, design).fit()
    return np.asarray(fitted.params, dtype="float64")


def _critical_value(degrees_of_freedom: float) -> float:
    if not np.isfinite(degrees_of_freedom) or degrees_of_freedom <= 0:
        return float("nan")
    return float(stats.t.ppf(1.0 - (1.0 - CONFIDENCE_LEVEL) / 2.0, degrees_of_freedom))


def _fit_statsmodels(
    y: np.ndarray,
    x: np.ndarray,
    covariance_method: str,
    groups: np.ndarray | None = None,
    second_groups: np.ndarray | None = None,
) -> FittedInference:
    design = sm.add_constant(np.asarray(x, dtype="float64"), has_constant="add")
    response = np.asarray(y, dtype="float64")
    base = sm.OLS(response, design).fit()

    if covariance_method == "HAC":
        fitted = sm.OLS(response, design).fit(
            cov_type="HAC",
            cov_kwds={
                "kernel": HAC_OPTIONS["kernel"],
                "maxlags": HAC_OPTIONS["maxlags"],
                "use_correction": HAC_OPTIONS["use_correction"],
            },
            use_t=HAC_OPTIONS["use_t"],
        )
        covariance = np.asarray(fitted.cov_params(), dtype="float64")
        degrees_of_freedom = float(fitted.df_resid)
        metadata = {
            "cov_type": "HAC",
            "covariance_method": "HAC",
            "covariance_options": dict(HAC_OPTIONS),
        }
    elif covariance_method == "calendar_month_clustered":
        if groups is None:
            raise ValueError("calendar-month cluster groups are required")
        fitted = sm.OLS(response, design).fit(
            cov_type="cluster",
            cov_kwds={
                "groups": np.asarray(groups),
                "use_correction": CLUSTER_OPTIONS["use_correction"],
                "df_correction": CLUSTER_OPTIONS["df_correction"],
            },
            use_t=CLUSTER_OPTIONS["use_t"],
        )
        covariance = np.asarray(fitted.cov_params(), dtype="float64")
        degrees_of_freedom = float(fitted.df_resid)
        metadata = {
            "cov_type": "cluster",
            "covariance_method": "calendar_month_clustered",
            "cluster_variable": "outcome_month",
            "covariance_options": dict(CLUSTER_OPTIONS),
        }
    elif covariance_method == "two_way_clustered":
        if groups is None or second_groups is None:
            raise ValueError("two-way cluster groups are required")
        covariance, _, _ = cov_cluster_2groups(
            base,
            np.asarray(groups),
            np.asarray(second_groups),
            use_correction=CLUSTER_OPTIONS["use_correction"],
        )
        covariance = np.asarray(covariance, dtype="float64")
        # statsmodels' two-group sandwich helper supplies the covariance.  The
        # project convention uses the conservative smaller cluster count for
        # Student-t critical values, while recording the requested correction.
        cluster_df = min(
            len(np.unique(groups)),
            len(np.unique(second_groups)),
        ) - 1
        degrees_of_freedom = float(cluster_df)
        metadata = {
            "cov_type": "two_way_cluster",
            "covariance_method": "two_way_clustered",
            "cluster_variable": "symbol × outcome_month",
            "covariance_options": dict(CLUSTER_OPTIONS),
        }
    else:
        raise ValueError(f"unsupported covariance method: {covariance_method}")

    return FittedInference(
        params=np.asarray(base.params, dtype="float64"),
        covariance=covariance,
        degrees_of_freedom=degrees_of_freedom,
        nobs=int(base.nobs),
        metadata=metadata,
    )


def coefficient_summary(fitted: FittedInference, coefficient_index: int = 1) -> dict[str, float]:
    estimate = float(fitted.params[coefficient_index])
    variance = float(fitted.covariance[coefficient_index, coefficient_index])
    standard_error = float(np.sqrt(variance)) if variance >= 0 else float("nan")
    t_stat = estimate / standard_error if standard_error > 0 else float("nan")
    critical = _critical_value(fitted.degrees_of_freedom)
    return {
        "alpha": float(fitted.params[0]),
        "beta": estimate,
        "standard_error": standard_error,
        "t_stat": t_stat,
        "ci_lower": estimate - critical * standard_error,
        "ci_upper": estimate + critical * standard_error,
        "nobs": fitted.nobs,
    }


def linear_combination_summary(fitted: FittedInference, weights: Iterable[float]) -> dict[str, float]:
    vector = np.asarray(tuple(weights), dtype="float64")
    estimate = float(vector @ fitted.params)
    variance = float(vector @ fitted.covariance @ vector)
    standard_error = float(np.sqrt(variance)) if variance >= 0 else float("nan")
    t_stat = estimate / standard_error if standard_error > 0 else float("nan")
    critical = _critical_value(fitted.degrees_of_freedom)
    return {
        "estimate": estimate,
        "standard_error": standard_error,
        "t_stat": t_stat,
        "ci_lower": estimate - critical * standard_error,
        "ci_upper": estimate + critical * standard_error,
        "nobs": fitted.nobs,
    }


def outcome_months_are_consecutive(months: Iterable[pd.Period]) -> bool:
    unique = sorted(set(months))
    if len(unique) < 2:
        return True
    expected = pd.period_range(unique[0], unique[-1], freq="M")
    return list(expected) == unique


def moving_block_bootstrap(
    data: pd.DataFrame,
    predictor_column: str,
    dependent_column: str,
    sample_start: pd.Period,
    sample_end: pd.Period,
    *,
    iterations: int = 5000,
    seed: int = 20260817,
    block_length: int = 12,
) -> BootstrapSummary:
    """Resample 12 calendar-month slots without compressing calendar gaps."""
    slots = pd.period_range(sample_start, sample_end, freq="M")
    if len(slots) < block_length:
        raise ValueError("sample has fewer calendar-month slots than block length")
    starts = np.arange(0, len(slots) - block_length + 1, dtype="int64")
    rng = np.random.Generator(np.random.PCG64(seed))
    coefficients: list[float] = []
    failed = 0
    outcome_values = data["outcome_month"].to_numpy()
    predictor_values = data[predictor_column].to_numpy(dtype="float64")
    dependent_values = data[dependent_column].to_numpy(dtype="float64")
    rows_by_slot = {
        month: np.flatnonzero(outcome_values == month)
        for month in slots
    }

    for _ in range(iterations):
        selected: list[pd.Period] = []
        while len(selected) < len(slots):
            start = int(rng.choice(starts))
            selected.extend(slots[start:start + block_length].tolist())
        selected = selected[:len(slots)]
        index_pieces = [rows_by_slot[month] for month in selected if len(rows_by_slot[month])]
        indices = np.concatenate(index_pieces) if index_pieces else np.array([], dtype="int64")
        if len(indices) < 2:
            failed += 1
            continue
        x = predictor_values[indices]
        y = dependent_values[indices]
        design = sm.add_constant(x, has_constant="add")
        if np.linalg.matrix_rank(design) < 2:
            failed += 1
            continue
        try:
            coefficients.append(float(np.linalg.lstsq(design, y, rcond=None)[0][1]))
        except (np.linalg.LinAlgError, ValueError):
            failed += 1

    successful = len(coefficients)
    if not successful:
        raise ValueError(f"all bootstrap draws failed: {failed}")
    values = np.asarray(coefficients, dtype="float64")
    metadata = {
        "bootstrap_method": "moving_block",
        "bootstrap_unit": "calendar_month",
        "block_length_months": block_length,
        "bootstrap_replications": iterations,
        "bootstrap_seed": seed,
        "rng": "numpy.Generator(PCG64)",
        "confidence_level": CONFIDENCE_LEVEL,
        "interval_method": "percentile",
        "successful_draws": successful,
        "failed_draws": failed,
    }
    return BootstrapSummary(
        standard_error=float(values.std(ddof=1)) if successful > 1 else float("nan"),
        ci_lower=float(np.percentile(values, 2.5)),
        ci_upper=float(np.percentile(values, 97.5)),
        successful_draws=successful,
        failed_draws=failed,
        metadata=metadata,
    )
