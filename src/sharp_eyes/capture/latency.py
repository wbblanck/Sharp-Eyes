"""Polymarket detection-latency report (audit recommendation 5).

Data API v2 poll
----------------

For each fill first returned by a fast trade poll, we know:

* ``ts``: the fill's block time (whole seconds);
* ``prev_poll_at``: the start of the previous poll of the same events, which
  did not return the fill;
* ``api_observed_at``: when the poll that first returned it came back.

So the fill became visible in the API somewhere in
``[prev_poll_at - ts, api_observed_at - ts]``. The upper bound is what a copy
signal built on this polling setup would actually experience; the lower bound
shows how much of that is the API itself rather than our poll interval.
Backfill rows and the first poll of each event carry no ``prev_poll_at`` and
are excluded.

Live-data websocket (RTDS)
--------------------------
A pushed fill's latency is simply ``ws_observed_at - ts``. Fills seen by both
feeds are compared head to head (``api_observed_at - ws_observed_at``, positive
when the socket was first), and coverage counts which feed saw what, over fills
whose block time falls inside a minute the socket was connected.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Connection, Engine, text

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
    rtds: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)

    def to_markdown(self) -> str:
        def row(name: str, d: dict[str, float | None]) -> str:
            cells = " | ".join(_fmt(d.get(k)) for k in ("p50", "p75", "p90", "p95", "p99", "max"))
            return f"| {name} | {cells} |"

        lines = [
            "# Polymarket detection latency",
            "",
            "## Data API v2 poll",
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
            lines.append("")
        if self.rtds:
            lines += self._rtds_markdown(row)
        return "\n".join(lines) + "\n"

    def _rtds_markdown(self, row: Callable[[str, dict[str, float | None]], str]) -> list[str]:
        r = self.rtds
        cov = r.get("coverage") or {}
        h2h = r.get("head_to_head") or {}
        return [
            "## Live-data websocket (RTDS)",
            "",
            f"Connected {_fmt(r.get('connected_minutes'))} min in this window "
            f"({r.get('drops', 0):,} drops). Fills pushed: {r.get('samples', 0):,}.",
            "",
            "| seconds | p50 | p75 | p90 | p95 | p99 | max |",
            "|---|---|---|---|---|---|---|",
            row("block time to push", r.get("latency") or {}),
            row("poll minus push", h2h),
            "",
            "Share of pushed fills seen within: "
            + ", ".join(f"{k}: {_pct(v)}" for k, v in (r.get("within") or {}).items()),
            "",
            f"Fills seen by both feeds: {cov.get('both', 0):,}; the socket was first for "
            f"{_pct(r.get('ws_first'))}. Socket only: {cov.get('ws_only', 0):,}. "
            f"Poll only: {cov.get('api_only', 0):,} "
            f"({cov.get('api_only_taker', 0):,} taker, {cov.get('api_only_maker', 0):,} maker).",
            "",
            "Coverage counts only fills whose block time falls in a minute the socket was",
            "connected. Many poll-only maker fills mean the socket carries taker fills only;",
            "many socket-only fills alongside poll-only ones mean the two feeds key the same",
            "fill differently and need a look.",
        ]


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
          AND api_observed_at >= :since AND api_observed_at < :until
    """
    upper_expr = "extract(epoch FROM api_observed_at - ts)"
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
                       to_char(date_trunc('hour', api_observed_at), 'YYYY-MM-DD HH24:00') AS hour,
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
        rtds = _rtds(conn, params)

    return LatencyReport(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        window_start=since.isoformat(timespec="seconds"),
        window_end=until.isoformat(timespec="seconds"),
        samples=int(n),
        upper=_floats(upper),
        lower=_floats(lower),
        share_visible_within=_floats(within),
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
        api_status_lag=_floats(dict(status)),
        rtds=rtds,
    )


def _floats(d: dict[str, Any]) -> dict[str, float | None]:
    return {k: (None if v is None else float(v)) for k, v in d.items()}


def _rtds(conn: Connection, params: dict[str, Any]) -> dict[str, Any]:
    segments = (
        conn.execute(
            text(
                f"""SELECT count(*) FILTER (WHERE ok) AS segments,
                       count(*) FILTER (WHERE NOT ok) AS drops,
                       sum(extract(epoch FROM finished_at - started_at)) FILTER (WHERE ok) / 60
                         AS connected_minutes
                FROM {SCHEMA}.poll_runs
                WHERE venue = 'POLYMARKET' AND job = 'rtds'
                  AND started_at >= :since AND started_at < :until"""
            ),
            params,
        )
        .mappings()
        .one()
    )
    if not segments["segments"] and not segments["drops"]:
        return {}  # Websocket not running in this window
    pushed = f"""FROM {SCHEMA}.trades WHERE venue = 'POLYMARKET'
                 AND ws_observed_at >= :since AND ws_observed_at < :until"""
    expr = "extract(epoch FROM ws_observed_at - ts)"
    n = conn.execute(text(f"SELECT count(*) {pushed}"), params).scalar_one()
    latency = conn.execute(text(f"SELECT {_pcts(expr)} {pushed}"), params).mappings().one()
    within = (
        conn.execute(
            text(
                "SELECT "
                + ", ".join(f'avg(({expr} <= {s})::int) AS "{s}s"' for s in (1, 2, 5, 10))
                + f" {pushed}"
            ),
            params,
        )
        .mappings()
        .one()
    )
    both = f"{pushed} AND api_observed_at IS NOT NULL"
    h2h_expr = "extract(epoch FROM api_observed_at - ws_observed_at)"
    h2h = conn.execute(text(f"SELECT {_pcts(h2h_expr)} {both}"), params).mappings().one()
    ws_first = conn.execute(
        text(f"SELECT avg((ws_observed_at < api_observed_at)::int) {both}"), params
    ).scalar_one()
    coverage = (
        conn.execute(
            text(
                f"""SELECT
                  count(*) FILTER (WHERE ws_observed_at IS NOT NULL
                                     AND api_observed_at IS NOT NULL) AS "both",
                  count(*) FILTER (WHERE api_observed_at IS NULL) AS ws_only,
                  count(*) FILTER (WHERE ws_observed_at IS NULL) AS api_only,
                  count(*) FILTER (WHERE ws_observed_at IS NULL AND seen_in_taker_feed)
                    AS api_only_taker,
                  count(*) FILTER (WHERE ws_observed_at IS NULL AND NOT seen_in_taker_feed)
                    AS api_only_maker
                FROM {SCHEMA}.trades t
                WHERE venue = 'POLYMARKET' AND ts >= :since AND ts < :until
                  AND EXISTS (
                    SELECT 1 FROM {SCHEMA}.poll_runs r
                    WHERE r.venue = 'POLYMARKET' AND r.job = 'rtds' AND r.ok
                      AND r.started_at <= t.ts AND r.finished_at >= t.ts)"""
            ),
            params,
        )
        .mappings()
        .one()
    )
    return {
        "connected_minutes": float(segments["connected_minutes"] or 0),
        "drops": int(segments["drops"]),
        "samples": int(n),
        "latency": _floats(dict(latency)),
        "within": _floats(dict(within)),
        "head_to_head": _floats(dict(h2h)),
        "ws_first": None if ws_first is None else float(ws_first),
        "coverage": {k: int(v) for k, v in dict(coverage).items()},
    }


def default_since(hours: float) -> datetime:
    return datetime.now(UTC) - timedelta(hours=hours)
