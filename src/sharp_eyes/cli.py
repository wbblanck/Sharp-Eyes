"""Command line entry point: ``sharp-eyes <command>``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from sharp_eyes.capture.latency import build_report, default_since
from sharp_eyes.capture.schema import SCHEMA
from sharp_eyes.capture.store import CaptureStore
from sharp_eyes.capture.worker import run_worker
from sharp_eyes.config import load_config
from sharp_eyes.db.session import make_engine

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def cmd_migrate(_: argparse.Namespace) -> int:
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    command.upgrade(cfg, "head")
    return 0


def cmd_capture(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    store = CaptureStore(make_engine())
    asyncio.run(run_worker(config, store, duration=args.duration))
    return 0


def cmd_latency(args: argparse.Namespace) -> int:
    report = build_report(make_engine(), default_since(args.hours))
    body = report.to_json() if args.format == "json" else report.to_markdown()
    if args.out:
        Path(args.out).write_text(body)
    else:
        sys.stdout.write(body)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Per-venue counts and last successful poll of each job."""
    engine = make_engine()
    since = datetime.now(UTC) - timedelta(hours=args.hours)
    with engine.connect() as conn:
        polls = conn.execute(
            text(
                f"""SELECT venue, job, max(finished_at) FILTER (WHERE ok) AS last_ok,
                       count(*) FILTER (WHERE NOT ok) AS failed, count(*) AS runs,
                       sum(changed) AS changed
                FROM {SCHEMA}.poll_runs WHERE started_at >= :since
                GROUP BY venue, job ORDER BY venue, job"""
            ),
            {"since": since},
        ).all()
        counts = conn.execute(
            text(
                f"""SELECT v.venue,
                  (SELECT count(*) FROM {SCHEMA}.events e WHERE e.venue = v.venue) AS events,
                  (SELECT count(*) FROM {SCHEMA}.markets m WHERE m.venue = v.venue) AS markets,
                  (SELECT count(*) FROM {SCHEMA}.book_snapshots b WHERE b.venue = v.venue) AS books,
                  (SELECT count(*) FROM {SCHEMA}.trades t WHERE t.venue = v.venue) AS trades
                FROM (VALUES ('POLYMARKET'), ('POLYMARKET_US'), ('KALSHI'), ('NOVIG')) v(venue)"""
            )
        ).all()
    print("venue          events  markets     books      trades")
    for venue, ev, mk, bk, tr in counts:
        print(f"{venue:<14}{ev:>7}{mk:>9}{bk:>10}{tr:>12}")
    print(f"\nPolls in the last {args.hours:g} h:")
    for venue, job, last_ok, failed, runs, changed in polls:
        last = last_ok.strftime("%Y-%m-%d %H:%M:%S") if last_ok else "never"
        print(
            f"  {venue:<14}{job:<9} last ok {last}  runs {runs:>6}  "
            f"failed {failed:>4}  changed {changed or 0:>8}"
        )
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    """Exit non-zero if any enabled venue has no successful book poll recently."""
    config = load_config(args.config)
    cap = config.capture
    enabled = [
        name
        for name, venue in (
            ("POLYMARKET", cap.polymarket),
            ("POLYMARKET_US", cap.polymarket_us),
            ("KALSHI", cap.kalshi),
            ("NOVIG", cap.novig),
        )
        if venue.enabled
    ]
    since = datetime.now(UTC) - timedelta(seconds=args.max_age)
    with make_engine().connect() as conn:
        healthy = {
            row[0]
            for row in conn.execute(
                text(
                    f"SELECT DISTINCT venue FROM {SCHEMA}.poll_runs "
                    "WHERE ok AND job IN ('books', 'catalog') AND finished_at >= :since"
                ),
                {"since": since},
            )
        }
    stale = [v for v in enabled if v not in healthy]
    if stale:
        print(f"unhealthy: no successful poll in {args.max_age}s for {', '.join(stale)}")
        return 1
    print("ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sharp-eyes")
    parser.add_argument("--config", help="YAML config path (default config/default.yaml)")
    parser.add_argument("--log-level", default="INFO")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate", help="apply database migrations").set_defaults(fn=cmd_migrate)

    p = sub.add_parser("capture", help="run the Phase 0 capture worker")
    p.add_argument(
        "--duration", type=float, help="stop after this many seconds (default: run forever)"
    )
    p.set_defaults(fn=cmd_capture)

    p = sub.add_parser("latency-report", help="Polymarket Data API v2 detection latency")
    p.add_argument("--hours", type=float, default=24.0)
    p.add_argument("--format", choices=("md", "json"), default="md")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_latency)

    p = sub.add_parser("status", help="capture counts and recent polls")
    p.add_argument("--hours", type=float, default=1.0)
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("health", help="exit 1 if a venue has stopped polling")
    p.add_argument("--max-age", type=int, default=900)
    p.set_defaults(fn=cmd_health)

    args = parser.parse_args(argv)
    _setup_logging(args.log_level)
    code: int = args.fn(args)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
