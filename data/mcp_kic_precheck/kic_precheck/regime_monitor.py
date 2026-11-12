"""Causal end-of-day market checks. No inference, network, or trading actions.

Each day's beta uses strictly earlier returns. Monthly thresholds use only earlier
dates. Prices are current adjusted-price vintages and baskets are current fixed
constituents: causal arithmetic is not a historical-vintage investment backtest.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, time, timezone
import math
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


def closed_prices(prices, now=None):
    """Conservative US close gate, including early-close days only after 16:15 ET.

    This is not an exchange calendar or a guarantee of vendor finalization.
    """
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ValueError("Observation time must have a timezone")
    eastern = observed.astimezone(ZoneInfo("America/New_York"))
    dates = prices.index.date
    allowed = dates <= eastern.date() if eastern.time() >= time(16, 15) else dates < eastern.date()
    return prices.loc[allowed]


@dataclass(frozen=True)
class MonitorConfig:
    beta_min_days: int = 60
    correlation_days: int = 60
    correlation_min_days: int = 50
    calibration_min_days: int = 126
    correlation_history_min_days: int = 30
    coverage_fraction: float = 0.8
    shock_quantile: float = 0.05
    hysteresis: float = 0.03

    def __post_init__(self):
        if not (2 <= self.beta_min_days and 2 <= self.correlation_min_days <= self.correlation_days):
            raise ValueError("Invalid history lengths")
        if self.calibration_min_days < 2 or self.correlation_history_min_days < 2:
            raise ValueError("Insufficient calibration lengths")
        if not (0 < self.coverage_fraction <= 1 and 0 < self.shock_quantile < 0.5 and 0 <= self.hysteresis < 1):
            raise ValueError("Invalid monitor configuration")


def causal_features(prices, chip_tickers, power_tickers, config=None):
    cfg = config or MonitorConfig()
    chip_tickers, power_tickers = list(chip_tickers), list(power_tickers)
    if not chip_tickers or not power_tickers or len(set(chip_tickers + power_tickers)) != len(chip_tickers + power_tickers):
        raise ValueError("Require nonempty disjoint baskets without duplicates")
    if not isinstance(prices.index, pd.DatetimeIndex) or not prices.index.is_unique or not prices.index.is_monotonic_increasing or prices.index.hasnans:
        raise ValueError("Prices need sorted unique valid dates")
    required = chip_tickers + power_tickers + ["SPY"]
    if "SPY" in chip_tickers + power_tickers or "SPY" not in prices:
        raise ValueError("SPY must be an independent market reference")
    px = prices.reindex(columns=required).astype(float)
    if np.isinf(px.to_numpy()).any() or ((px <= 0) & px.notna()).any().any():
        raise ValueError("Prices must be positive finite values or missing")
    ret = np.log(px / px.shift(1))
    x = ret["SPY"]
    residuals, counts = {}, {}
    for ticker in chip_tickers + power_tickers:
        y = ret[ticker]
        valid = x.notna() & y.notna()
        n = valid.astype(int).cumsum()
        xx, yy = x.where(valid, 0), y.where(valid, 0)
        sx, sy = xx.cumsum(), yy.cumsum()
        denominator = (xx * xx).cumsum() - sx * sx / n.replace(0, np.nan)
        numerator = (xx * yy).cumsum() - sx * sy / n.replace(0, np.nan)
        beta = (numerator / denominator.where(denominator > 1e-14)).shift(1)
        beta = beta.where(n.shift(1) >= cfg.beta_min_days)
        residuals[ticker] = y - beta * x
        counts[ticker] = beta.notna() & valid
    residuals = pd.DataFrame(residuals, index=px.index)
    actual = np.expm1(ret)
    frame = pd.DataFrame(index=px.index)
    for label, tickers in (("chip", chip_tickers), ("power", power_tickers)):
        minimum = math.ceil(len(tickers) * cfg.coverage_fraction)
        available = residuals[tickers].notna().sum(axis=1)
        frame[label + "_available"] = available
        frame[label + "_resid"] = residuals[tickers].mean(axis=1).where(available >= minimum)
        actual_available = actual[tickers].notna().sum(axis=1)
        frame[label + "_return"] = actual[tickers].mean(axis=1).where(actual_available >= minimum)
    frame["spy_return"] = actual["SPY"]
    frame["link"] = frame["chip_resid"].rolling(cfg.correlation_days, min_periods=cfg.correlation_min_days).corr(frame["power_resid"])
    return frame


def monitor_history(prices, chip_tickers, power_tickers, config=None):
    """Prefix-invariant features, calibration and signals. A row is known after close."""
    cfg = config or MonitorConfig()
    frame = causal_features(prices, chip_tickers, power_tickers, cfg)
    output, calibrations = [], {}
    state, previous_link = None, None
    for date, row in frame.iterrows():
        month = date.strftime("%Y-%m")
        if month not in calibrations:
            past = frame.loc[frame.index < date]
            chips, links = past["chip_resid"].dropna(), past["link"].dropna()
            if len(chips) >= cfg.calibration_min_days and len(links) >= cfg.correlation_history_min_days:
                calibrations[month] = {"calibration_start": past.index[0].date().isoformat(),
                                       "calibration_end": past.index[-1].date().isoformat(),
                                       "calibration_chip_days": len(chips), "calibration_link_days": len(links),
                                       "link_cut": float(links.median()),
                                       "shock_cut": float(chips.quantile(cfg.shock_quantile))}
            else:
                calibrations[month] = None
        calibration = calibrations[month]
        eligible = calibration is not None and pd.notna(row["link"]) and pd.notna(row["chip_resid"]) and pd.notna(row["chip_return"])
        item = {"date": date.date().isoformat(), **row.to_dict(), "eligible": bool(eligible),
                "regime_change": False, "enter_high": False, "chip_shock": False,
                "regime_high": None, "calibration_rebased_state": False}
        if calibration:
            item.update(calibration)
        if not eligible:
            state, previous_link = None, None
            output.append(item)
            continue
        cut, value, band = calibration["link_cut"], float(row["link"]), cfg.hysteresis
        # A changed threshold alone must not manufacture a market transition.
        if previous_link is not None:
            implied = 1 if previous_link >= cut + band else (0 if previous_link <= cut - band else state)
            if state is not None and implied != state:
                state = implied
                item["calibration_rebased_state"] = True
        new = 1 if value >= cut + band else (0 if value <= cut - band else state)
        changed = state is not None and new is not None and new != state
        state = new if new is not None else state
        item.update(regime_change=bool(changed), enter_high=bool(changed and new == 1),
                    regime_high=None if state is None else bool(state),
                    chip_shock=bool(row["chip_resid"] <= calibration["shock_cut"] and row["chip_resid"] < 0 and row["chip_return"] < 0))
        previous_link = value
        output.append(item)
    result = pd.DataFrame(output)
    if result.empty:
        return result
    return result.set_index(pd.to_datetime(result.pop("date")))


def signal_events(history):
    events = []
    for date, row in history.iterrows():
        if not row["eligible"]:
            continue
        common = {"date": date.date().isoformat(), "available_after": "US market close; use from the following session",
                  "calibration_end": row["calibration_end"], "method": "causal_monthly_v1"}
        if row["regime_change"]:
            events.append({**common, "kind": "국면 바뀜",
                           "detail": f"시장 조정 동조화 {row['link']:.3f}, 이전 자료 중간값 {row['link_cut']:.3f}; "
                                     + ("높은 동조화로 전환" if row["regime_high"] else "낮은 동조화로 전환")})
        if row["chip_shock"]:
            events.append({**common, "kind": "칩 충격 날",
                           "detail": f"시장 조정 칩 등락 {np.expm1(row['chip_resid']) * 100:.2f}%, "
                                     f"사전 하위 5% 기준 {np.expm1(row['shock_cut']) * 100:.2f}%"})
    return events


def latest_check(history, config=None):
    cfg = config or MonitorConfig()
    if history.empty:
        raise ValueError("No market history")
    row, date = history.iloc[-1], history.index[-1]
    eligible = bool(row["eligible"])
    finite = lambda value: float(value) if pd.notna(value) and np.isfinite(value) else None
    return {"as_of": date.date().isoformat(), "status": "ready" if eligible else "insufficient_history_or_coverage",
            "regime_now": ("과거 중간수준보다 동조화가 높은 국면" if row["regime_high"] is True or row["regime_high"] == True
                           else "과거 중간수준보다 동조화가 낮은 국면" if row["regime_high"] is False or row["regime_high"] == False else "판정 보류"),
            "link_now": finite(row["link"]), "link_cut": finite(row.get("link_cut")),
            "distance_to_cut": finite(row["link"] - row.get("link_cut", np.nan)),
            "shock_cut_pct": None if not eligible else float(np.expm1(row["shock_cut"]) * 100),
            "calibration_end": row.get("calibration_end") if eligible else None,
            "method": "causal_monthly_v1", "config": asdict(cfg),
            "signal_available": "미국 시장 종가 확정 후; 다음 거래일부터 활용",
            "early_warning_performance_established": False,
            "limitations": ["Fixed current constituents; no historical membership or publication-vintage reconstruction.",
                            "Adjusted prices are current-vintage, not independently archived historical releases.",
                            "High co-movement is descriptive; it is not itself proof of abnormality or a loss prediction."]}
