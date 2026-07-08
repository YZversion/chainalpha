"""事件研究：信号组 vs 随机对照，输出留/删结论。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats

from chainalpha.factors.events import SignalSpec, apply_signal
from chainalpha.factors.forward_return import (
    DEFAULT_HORIZONS,
    add_forward_returns,
    extract_signal_returns,
    mean_forward_returns,
)

Verdict = Literal["KEEP", "DELETE", "INSUFFICIENT_SAMPLE"]


@dataclass
class HorizonStats:
    horizon: int
    signal_mean: float
    random_mean: float
    excess: float
    signal_median: float
    signal_count: int
    t_stat: float
    p_value: float


@dataclass
class EventStudyResult:
    signal_name: str
    signal_description: str
    start_date: str
    end_date: str
    horizons: tuple[int, ...]
    signal_count: int
    horizon_stats: list[HorizonStats] = field(default_factory=list)
    verdict: Verdict = "INSUFFICIENT_SAMPLE"
    verdict_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "signal_name": self.signal_name,
            "signal_description": self.signal_description,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "signal_count": self.signal_count,
            "verdict": self.verdict,
            "verdict_reason": self.verdict_reason,
            "horizons": [
                {
                    "horizon": h.horizon,
                    "signal_mean_pct": round(h.signal_mean * 100, 4),
                    "random_mean_pct": round(h.random_mean * 100, 4),
                    "excess_pct": round(h.excess * 100, 4),
                    "signal_median_pct": round(h.signal_median * 100, 4),
                    "signal_count": h.signal_count,
                    "t_stat": round(h.t_stat, 4) if not np.isnan(h.t_stat) else None,
                    "p_value": round(h.p_value, 4) if not np.isnan(h.p_value) else None,
                }
                for h in self.horizon_stats
            ],
        }


@dataclass(frozen=True)
class KillCriteria:
    """无 Edge 判定阈值（固定，验证阶段不调参）。"""

    min_signal_count: int = 30
    primary_horizon: int = 5
    delete_if_mean_below: float = 0.0  # 主 horizon 平均收益 < 0 → 删
    delete_if_excess_below: float = 0.001  # 相对随机超额 < 0.1% → 删
    strong_delete_if_mean_below: float = -0.005  # 如 -0.5% 以下直接删


def _filter_date_range(panel: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    mask = (panel["trade_date"] >= start_ts) & (panel["trade_date"] <= end_ts)
    return panel.loc[mask].copy()


def sample_random_baseline(
    panel_with_fwd: pd.DataFrame,
    n_samples: int,
    exclude_mask: pd.Series,
    horizons: tuple[int, ...],
    rng: np.random.Generator,
) -> pd.DataFrame:
    """从同 panel 随机抽 (symbol, date)，排除信号日，样本量与信号组对齐。"""
    eligible = panel_with_fwd.loc[~exclude_mask.fillna(False)].dropna(subset=[f"fwd_ret_{horizons[0]}"])
    if eligible.empty or n_samples <= 0:
        return pd.DataFrame()
    replace = n_samples > len(eligible)
    idx = rng.choice(eligible.index.to_numpy(), size=n_samples, replace=replace)
    return eligible.loc[idx].copy()


def _horizon_stat(
    signal_rets: pd.Series,
    random_rets: pd.Series,
    horizon: int,
) -> HorizonStats:
    sig = signal_rets.dropna()
    rnd = random_rets.dropna()
    sig_mean = float(sig.mean()) if len(sig) else float("nan")
    rnd_mean = float(rnd.mean()) if len(rnd) else float("nan")
    excess = sig_mean - rnd_mean if not (np.isnan(sig_mean) or np.isnan(rnd_mean)) else float("nan")
    sig_median = float(sig.median()) if len(sig) else float("nan")

    if len(sig) >= 2 and len(rnd) >= 2:
        t_stat, p_value = stats.ttest_ind(sig, rnd, equal_var=False, nan_policy="omit")
        t_stat_f = float(t_stat)
        p_value_f = float(p_value)
    else:
        t_stat_f = float("nan")
        p_value_f = float("nan")

    return HorizonStats(
        horizon=horizon,
        signal_mean=sig_mean,
        random_mean=rnd_mean,
        excess=excess,
        signal_median=sig_median,
        signal_count=len(sig),
        t_stat=t_stat_f,
        p_value=p_value_f,
    )


def judge_verdict(
    horizon_stats: list[HorizonStats],
    criteria: KillCriteria,
) -> tuple[Verdict, str]:
    primary = next((h for h in horizon_stats if h.horizon == criteria.primary_horizon), None)
    if primary is None or primary.signal_count < criteria.min_signal_count:
        return "INSUFFICIENT_SAMPLE", (
            f"样本数 {primary.signal_count if primary else 0} < {criteria.min_signal_count}"
        )

    mean_5 = primary.signal_mean
    excess_5 = primary.excess

    if mean_5 <= criteria.strong_delete_if_mean_below:
        return "DELETE", (
            f"{criteria.primary_horizon}日均收益 {mean_5:.2%} ≤ "
            f"{criteria.strong_delete_if_mean_below:.2%}，无 Edge，直接删"
        )
    if mean_5 < criteria.delete_if_mean_below and excess_5 < criteria.delete_if_excess_below:
        return "DELETE", (
            f"{criteria.primary_horizon}日均收益 {mean_5:.2%} < 0 且超额 {excess_5:.2%} "
            f"< {criteria.delete_if_excess_below:.2%}"
        )
    if mean_5 >= criteria.delete_if_mean_below and excess_5 >= criteria.delete_if_excess_below:
        return "KEEP", (
            f"{criteria.primary_horizon}日均收益 {mean_5:.2%}，超额 {excess_5:.2%}，暂留"
        )
    return "DELETE", (
        f"{criteria.primary_horizon}日未同时满足均值≥0与超额≥{criteria.delete_if_excess_below:.2%}"
    )


def run_event_study(
    panel: pd.DataFrame,
    spec: SignalSpec,
    start_date: str,
    end_date: str,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    criteria: KillCriteria | None = None,
    random_seed: int = 42,
) -> EventStudyResult:
    """对单一信号做事件研究（2020–2025 等窗口由 start/end 指定）。"""
    criteria = criteria or KillCriteria()
    rng = np.random.default_rng(random_seed)

    scoped = _filter_date_range(panel, start_date, end_date)
    if scoped.empty:
        return EventStudyResult(
            signal_name=spec.name,
            signal_description=spec.description,
            start_date=start_date,
            end_date=end_date,
            horizons=horizons,
            signal_count=0,
            verdict="INSUFFICIENT_SAMPLE",
            verdict_reason="日期范围内无数据",
        )

    with_fwd = add_forward_returns(scoped, horizons=horizons)
    signal_mask = apply_signal(scoped, spec)
    signal_rows = extract_signal_returns(with_fwd, signal_mask, horizons=horizons)
    n_signal = len(signal_rows)

    random_rows = sample_random_baseline(
        with_fwd,
        n_samples=n_signal,
        exclude_mask=signal_mask,
        horizons=horizons,
        rng=rng,
    )

    h_stats: list[HorizonStats] = []
    for h in horizons:
        col = f"fwd_ret_{h}"
        h_stats.append(
            _horizon_stat(
                signal_rows[col] if not signal_rows.empty else pd.Series(dtype=float),
                random_rows[col] if not random_rows.empty else pd.Series(dtype=float),
                horizon=h,
            )
        )

    verdict, reason = judge_verdict(h_stats, criteria)
    return EventStudyResult(
        signal_name=spec.name,
        signal_description=spec.description,
        start_date=start_date,
        end_date=end_date,
        horizons=horizons,
        signal_count=n_signal,
        horizon_stats=h_stats,
        verdict=verdict,
        verdict_reason=reason,
    )
