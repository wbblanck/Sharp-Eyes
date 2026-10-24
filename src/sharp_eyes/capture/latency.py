"""Polymarket Data API v2 detection-latency report (audit recommendation 5).

For each fill first returned by a fast trade poll, we know:

* ``ts``: the fill's block time (whole seconds);
* ``prev_poll_at``: the start of the previous poll of the same events, which
  did not return the fill;
* ``observed_at``: when the poll that first returned it came back.

So the fill became visible in the API somewhere in
``[prev_poll_at - ts, observed_at - ts]``. The upper bound is what a copy
signal built on this polling setup would actually experience; the lower bound
shows how much of that is the API itself rather than our poll interval.
Backfill rows and the first poll of each event carry no ``prev_poll_at`` and
are excluded.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, text

from sharp_eyes.capture.schema import SCHEMA

PERCENTILES = (0.5, 0.75, 0.9, 0.95, 0.99)


@dataclass
class LatencyReport:
    generated_at: str
    window_start: str
    window_end: str
    samples: int
    upper: dict[str, float | None]
    lower: dict[str, float | None]
    share_visible_within: dict[str, float | None]
    by_hour: list[dict[str, Any]] = field(default_factory=list)
    trade_polls: dict[str, Any] = field(default_factory=dict)
    api_status_lag: dict[str, float | None] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)

    def to_markdown(self) -> str:
        def row(name: str, d: dict[str, float | None]) -> str:
            cells = " | ".join(_fmt(d.get(k)) for k in ("p50", "p75", "p90", "p95", "p99", "max"))
            return f"| {name} | {cells} |"

        lines = [
            "# Polymarket Data API v2 detection latency",
            "",
            f"Window: {self.window_start} to {self.window_end} (UTC). "
            f"Samples: {self.samples:,} fills.",
            "",
            "Seconds from a fill's block time until our poll returned it. The upper bound is",
            "what a copy signal would experience with this setup; the lower bound is the",
            "earliest the fill could have become visible (the previous poll did not return it).",
            "",
            "| bound | p50 | p75 | p90 | p95 | p99 | max |",
            "|---|---|---|---|---|---|---|",
            row("upper (observed)", self.upper),
            row("lower (API-only)", self.lower),
            "",
            "Share of fills seen within (upper bound): "
            + ", ".join(f"{k}: {_pct(v)}" for k, v in self.share_visible_within.items()),
            "",
        ]
        if self.trade_polls:
            tp = self.trade_polls
            lines += [
                f"Trade polls: {tp.get('polls', 0):,} ({tp.get('failed', 0):,} failed), "
                f"median interval {_fmt(tp.get('median_interval'))} s, "
                f"longest gap {_fmt(tp.get('max_gap'))} s.",
                "",
            ]
        if self.api_status_lag:
            lines += [
                "API self-reported serving lag (`/v2/status`): "
                + ", ".join(f"{k} {_fmt(v)} s" for k, v in self.api_status_lag.items()),
                "",
            ]
        if self.by_hour:
            lines += ["| hour (UTC) | fills | upper p50 | upper p90 |", "|---|---|---|---|"]
            lines += [
                f"| {h['hour']} | {h['samples']:,} | {_fmt(h['p50'])} | {_fmt(h['p90'])} |"
                for h in self.by_hour
            ]
        return "\n".join(lines) + "\n"


def _fmt(v: Any) -> str:
    return "n/a" if v is None else f"{float(v):.1f}"


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100:.1f}%"


def _pcts(column: str) -> str:
    parts = [
        f"percentile_cont({p}) WITHIN GROUP (ORDER BY {column}) AS p{round(p * 100)}"
        for p in PERCENTILES
    ]
    return ", ".join([*parts, f"max({column}) AS max"])


def build_report(engine: Engine, since: datetime, until: datetime | None = None) -> LatencyReport:
    until = until or datetime.now(UTC)
    params = {"since": since, "until": until}
    base = f"""
        FROM {SCHEMA}.trades
        WHERE venue = 'POLYMARKET' AND prev_poll_at IS NOT NULL
          AND observed_at >= :since AND observed_at < :until
    """
    upper_expr = "extract(epoch FROM observed_at - ts)"
    lower_expr = "greatest(0, extract(epoch FROM prev_poll_at - ts))"
    with engine.connect() as conn:
        n = conn.execute(text(f"SELECT count(*) {base}"), params).scalar_one()
        upper = dict(
            conn.execute(text(f"SELECT {_pcts(upper_expr)} {base}"), params).mappings().one()
        )
        lower = dict(
            conn.execute(text(f"SELECT {_pcts(lower_expr)} {base}"), params).mappings().one()
        )
        within = dict(
            conn.execute(
                text(
                    "SELECT "
                    + ", ".join(
                        f'avg(({upper_expr} <= {s})::int) AS "{s}s"' for s in (5, 10, 30, 60)
                    )
                    + f" {base}"
                ),
                params,
            )
            .mappings()
            .one()
        )
        hours = (
            conn.execute(
                text(
                    f"""SELECT
                       to_char(date_trunc('hour', observed_at), 'YYYY-MM-DD HH24:00') AS hour,
                       count(*) AS samples,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY {upper_expr}) AS p50,
                       percentile_cont(0.9) WITHIN GROUP (ORDER BY {upper_expr}) AS p90
                {base} GROUP BY 1 ORDER BY 1"""
                ),
                params,
            )
            .mappings()
            .all()
        )
        polls = (
            conn.execute(
                text(
                    f"""WITH p AS (
                      SELECT ok, started_at,
                             extract(epoch FROM started_at
                                     - lag(started_at) OVER (ORDER BY started_at)) AS gap
                      FROM {SCHEMA}.poll_runs
                      WHERE venue = 'POLYMARKET' AND job = 'trades'
                        AND started_at >= :since AND started_at < :until)
                    SELECT count(*) AS polls, count(*) FILTER (WHERE NOT ok) AS failed,
                           percentile_cont(0.5) WITHIN GROUP (ORDER BY gap) AS median_interval,
                           max(gap) AS max_gap FROM p"""
                ),
                params,
            )
            .mappings()
            .one()
        )
        status = (
            conn.execute(
                text(
                    f"""SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY lag_seconds) AS p50,
                           percentile_cont(0.9) WITHIN GROUP (ORDER BY lag_seconds) AS p90,
                           max(lag_seconds) AS max
                    FROM {SCHEMA}.api_status_samples
                    WHERE venue = 'POLYMARKET' AND observed_at >= :since AND observed_at < :until"""
                ),
                params,
            )
            .mappings()
            .one()
        )

    def floats(d: dict[str, Any]) -> dict[str, float | None]:
        return {k: (None if v is None else float(v)) for k, v in d.items()}

    return LatencyReport(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        window_start=since.isoformat(timespec="seconds"),
        window_end=until.isoformat(timespec="seconds"),
        samples=int(n),
        upper=floats(upper),
        lower=floats(lower),
        share_visible_within=floats(within),
        by_hour=[
            {
                "hour": h["hour"],
                "samples": int(h["samples"]),
                "p50": float(h["p50"]),
                "p90": float(h["p90"]),
            }
            for h in hours
        ],
        trade_polls={k: (float(v) if v is not None else None) for k, v in dict(polls).items()},
        api_status_lag=floats(dict(status)),
    )


def default_since(hours: float) -> datetime:
    return datetime.now(UTC) - timedelta(hours=hours)
