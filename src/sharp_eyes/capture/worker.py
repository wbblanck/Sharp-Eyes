"""The always-on capture worker.

One :class:`VenueRunner` per venue runs independent loops (catalog, books,
trades, plus Polymarket status and history backfill). A failure in one loop is
logged and recorded in ``capture.poll_runs`` and the loop carries on; nothing
in one venue can stall another. All state needed to resume (checkpoints, last
stored book hashes, the catalog) lives in Postgres, so a restart loses at most
the polls that were in flight.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import time
from collections.abc import Awaitable, Callable, Coroutine
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sharp_eyes.capture.http import VenueHttp
from sharp_eyes.capture.records import BetType, BookSnapshot, MarketRecord, TradeRecord
from sharp_eyes.capture.store import CaptureStore
from sharp_eyes.capture.venues import kalshi, novig, polymarket, polymarket_rtds, polymarket_us
from sharp_eyes.capture.venues.base import VenueAdapter, chunks
from sharp_eyes.config import AppConfig, BookScope, CaptureConfig, VenueCaptureConfig

log = logging.getLogger(__name__)

OPEN_STATUSES = frozenset({"open", "active"})
BOOK_BATCH = 200  # Markets per fetch/store round (Polymarket: 400 tokens < 500 cap)


def in_scope(market: MarketRecord, scope: BookScope) -> bool:
    if scope is BookScope.CORE:
        return market.is_core
    if scope is BookScope.GAME:
        return market.bet_type is not BetType.PROP
    return True


class VenueRunner:
    def __init__(
        self,
        adapter: VenueAdapter,
        venue_cfg: VenueCaptureConfig,
        capture_cfg: CaptureConfig,
        store: CaptureStore,
    ) -> None:
        self.adapter = adapter
        self.venue = adapter.venue.value
        self.cfg = venue_cfg
        self.capture = capture_cfg
        self.store = store
        self.markets: dict[str, MarketRecord] = {}
        self.event_ids: set[str] = set()
        self.catalog_ready = asyncio.Event()
        self._book_due: dict[str, float] = {}
        self._book_hashes: dict[str, str] = {}

    # -- helpers -----------------------------------------------------------

    def _window(self) -> tuple[datetime, datetime]:
        now = datetime.now(UTC)
        return (
            now - timedelta(hours=self.capture.window_past_hours),
            now + timedelta(days=self.capture.window_future_days),
        )

    def live_markets(self) -> list[MarketRecord]:
        start, end = self._window()
        return [
            m
            for m in self.markets.values()
            if m.start_time is not None
            and start <= m.start_time <= end
            and m.status.lower() in OPEN_STATUSES
        ]

    def book_markets(self) -> list[MarketRecord]:
        return [m for m in self.live_markets() if in_scope(m, self.cfg.book_scope)]

    async def _run_job(
        self, job: str, fn: Callable[[], Awaitable[tuple[int, int]]], *, record: bool = True
    ) -> bool:
        started = datetime.now(UTC)
        requests_before = self.adapter.request_count()
        try:
            items, changed = await fn()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("%s %s failed", self.venue, job)
            await asyncio.to_thread(
                self.store.record_poll,
                self.venue,
                job,
                started,
                datetime.now(UTC),
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
            )
            return False
        if record and (items or changed or job != "books"):
            await asyncio.to_thread(
                self.store.record_poll,
                self.venue,
                job,
                started,
                datetime.now(UTC),
                ok=True,
                requests=self.adapter.request_count() - requests_before,
                items=items,
                changed=changed,
            )
        return True

    async def _every(
        self, seconds: float, job: str, fn: Callable[[], Awaitable[tuple[int, int]]]
    ) -> None:
        while True:
            began = time.monotonic()
            await self._run_job(job, fn)
            await asyncio.sleep(max(0.0, seconds - (time.monotonic() - began)))

    # -- jobs --------------------------------------------------------------

    async def catalog_once(self) -> tuple[int, int]:
        start, end = self._window()
        catalog = await self.adapter.fetch_catalog(start, end)
        changed = await asyncio.to_thread(
            self.store.upsert_catalog,
            self.venue,
            catalog,
            self.adapter.stable_view,
            datetime.now(UTC),
        )
        self.markets = {m.market_id: m for m in catalog.markets}
        self.event_ids = {e.event_id for e in catalog.events}
        self.catalog_ready.set()
        log.info(
            "%s catalog: %d events, %d markets (%d in book scope), %d changed",
            self.venue,
            len(catalog.events),
            len(catalog.markets),
            len(self.book_markets()),
            changed,
        )
        return len(catalog.events) + len(catalog.markets), changed

    async def books_once(self) -> tuple[int, int]:
        now_mono, now = time.monotonic(), datetime.now(UTC)
        due = []
        for m in self.book_markets():
            if self._book_due.get(m.market_id, 0.0) <= now_mono:
                assert m.start_time is not None
                minutes = (m.start_time - now).total_seconds() / 60
                self._book_due[m.market_id] = now_mono + self.capture.books_interval(minutes)
                due.append(m)
        # Nearest kickoff first, stored in batches so a long sweep (hundreds of
        # Novig ladders after a restart) saves as it goes.
        due.sort(key=lambda m: m.start_time or now)
        fetched = stored = 0
        for batch in chunks(due, BOOK_BATCH):
            snaps = await self.adapter.fetch_books(batch)
            changed = self._changed(snaps)
            await asyncio.to_thread(self.store.insert_books, changed)
            fetched, stored = fetched + len(snaps), stored + len(changed)
        return fetched, stored

    def _changed(self, snaps: list[BookSnapshot]) -> list[BookSnapshot]:
        out = []
        for snap in snaps:
            h = snap.content_hash()
            if self._book_hashes.get(snap.book_key) != h:
                self._book_hashes[snap.book_key] = h
                out.append(snap)
        return out

    async def trades_once(self) -> tuple[int, int]:
        markets = self.live_markets()
        if self.cfg.book_scope is not BookScope.ALL and not isinstance(
            self.adapter, polymarket.PolymarketAdapter
        ):
            # Execution venues: trades for the markets whose books we capture.
            markets = [m for m in markets if in_scope(m, self.cfg.book_scope)]
        if not markets:
            return 0, 0
        checkpoints = await asyncio.to_thread(self.store.get_checkpoints, self.venue)
        batch = await self.adapter.fetch_trades(markets, checkpoints)
        new = await asyncio.to_thread(self.store.insert_trades, batch.trades)
        await asyncio.to_thread(self.store.set_checkpoints, self.venue, batch.checkpoints)
        return len(batch.trades), new

    # -- loops -------------------------------------------------------------

    async def catalog_loop(self) -> None:
        while True:
            ok = await self._run_job("catalog", self.catalog_once)
            await asyncio.sleep(self.capture.catalog_seconds if ok else 30)

    async def books_loop(self) -> None:
        await self.catalog_ready.wait()
        self._book_hashes = await asyncio.to_thread(self.store.latest_book_hashes, self.venue)
        tick = min(t.books_seconds for t in self.capture.tiers) if self.capture.tiers else 15
        await self._every(min(tick, 5), "books", self.books_once)

    async def trades_loop(self) -> None:
        await self.catalog_ready.wait()
        await self._every(self.cfg.trades_seconds, "trades", self.trades_once)

    def tasks(self) -> list[Coroutine[Any, Any, None]]:
        return [self.catalog_loop(), self.books_loop(), self.trades_loop()]


class PolymarketRunner(VenueRunner):
    adapter: polymarket.PolymarketAdapter
    cfg: Any

    async def status_once(self) -> tuple[int, int]:
        data = await self.adapter.fetch_status()
        lag = (data.get("serving") or {}).get("lag_seconds")
        await asyncio.to_thread(
            self.store.add_status_sample,
            self.venue,
            datetime.now(UTC),
            Decimal(str(lag)) if lag is not None else None,
            data,
        )
        return 1, 0

    async def trades_loop(self) -> None:
        await self.catalog_ready.wait()
        # Fast loop: each pass is a few requests, and a short interval is what
        # makes the visibility-latency measurement tight.
        while True:
            began = time.monotonic()
            await self._run_job("trades", self.trades_once)
            await asyncio.sleep(max(0.0, self.cfg.trades_seconds - (time.monotonic() - began)))

    async def status_loop(self) -> None:
        while True:
            await self._run_job("status", self.status_once, record=False)
            await asyncio.sleep(self.cfg.status_seconds)

    async def backfill_loop(self) -> None:
        """Pull each event's full trade history once (trader-price evidence only)."""
        await self.catalog_ready.wait()
        while True:
            checkpoints = await asyncio.to_thread(self.store.get_checkpoints, self.venue)
            pending = sorted(e for e in self.event_ids if f"backfill:{e}" not in checkpoints)
            for event_id in pending:

                async def run(event_id: str = event_id) -> tuple[int, int]:
                    trades = await self.adapter.backfill_event(event_id)
                    new = await asyncio.to_thread(self.store.insert_trades, trades)
                    await asyncio.to_thread(
                        self.store.set_checkpoints,
                        self.venue,
                        {f"backfill:{event_id}": datetime.now(UTC).isoformat()},
                    )
                    return len(trades), new

                await self._run_job("backfill", run)
            await asyncio.sleep(60)

    async def _safely(self, what: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        try:
            await asyncio.to_thread(fn, *args, **kwargs)
        except Exception:
            log.exception("%s %s failed", self.venue, what)

    async def rtds_loop(self, stream: polymarket_rtds.RtdsTradeStream | None = None) -> None:
        """Websocket fills for catalog markets, merged with the poll's rows in the store."""
        await self.catalog_ready.wait()
        stream = stream or polymarket_rtds.RtdsTradeStream()

        def wanted(trade: TradeRecord) -> bool:
            return trade.market_id in self.markets  # NFL catalog markets only

        async def store(trades: list[TradeRecord]) -> None:
            # A failed write is not retried: the poll stores the same fills.
            await self._safely("storing RTDS trades", self.store.insert_trades, trades)

        async def record(session: polymarket_rtds.Session) -> None:
            await self._safely(
                "recording an RTDS session",
                self.store.record_poll,
                self.venue,
                "rtds",
                session.started_at,
                session.finished_at,
                ok=session.ok,
                items=session.messages,
                changed=session.kept,
                error=session.error,
            )

        while True:
            try:
                await stream.run(wanted, store, record)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("RTDS stream crashed; restarting")
                await asyncio.sleep(5)

    def tasks(self) -> list[Coroutine[Any, Any, None]]:
        out = [*super().tasks(), self.status_loop()]
        if self.cfg.backfill_history:
            out.append(self.backfill_loop())
        if self.cfg.rtds:
            out.append(self.rtds_loop())
        return out


def build_runners(config: AppConfig, store: CaptureStore) -> list[VenueRunner]:
    cap = config.capture
    runners: list[VenueRunner] = []
    if cap.polymarket.enabled:
        pm = cap.polymarket
        adapter = polymarket.PolymarketAdapter(
            VenueHttp("POLYMARKET", polymarket.GAMMA, rate_per_second=pm.rate_per_second),
            data_http=VenueHttp(
                "POLYMARKET", polymarket.DATA, rate_per_second=pm.data_rate_per_second
            ),
            clob_http=VenueHttp(
                "POLYMARKET", polymarket.CLOB, rate_per_second=pm.clob_rate_per_second
            ),
            max_levels=pm.max_levels,
            trade_overlap_seconds=pm.trade_overlap_seconds,
        )
        runners.append(PolymarketRunner(adapter, pm, cap, store))
    if cap.polymarket_us.enabled:
        us = cap.polymarket_us
        runners.append(
            VenueRunner(
                polymarket_us.PolymarketUSAdapter(
                    VenueHttp(
                        "POLYMARKET_US", polymarket_us.GATEWAY, rate_per_second=us.rate_per_second
                    ),
                    max_levels=us.max_levels,
                    concurrency=us.concurrency,
                ),
                us,
                cap,
                store,
            )
        )
    if cap.kalshi.enabled:
        k = cap.kalshi
        runners.append(
            VenueRunner(
                kalshi.KalshiAdapter(
                    VenueHttp("KALSHI", kalshi.API, rate_per_second=k.rate_per_second),
                    series=k.series,
                    max_levels=k.max_levels,
                ),
                k,
                cap,
                store,
            )
        )
    if cap.novig.enabled:
        n = cap.novig
        runners.append(
            VenueRunner(
                novig.NovigAdapter(
                    VenueHttp("NOVIG", novig.API, rate_per_second=n.rate_per_second),
                    market_types=n.market_types,
                    max_levels=n.max_levels,
                    concurrency=n.concurrency,
                ),
                n,
                cap,
                store,
            )
        )
    return runners


async def run_worker(
    config: AppConfig, store: CaptureStore, *, duration: float | None = None
) -> None:
    runners = build_runners(config, store)
    tasks = [asyncio.create_task(coro) for r in runners for coro in r.tasks()]
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):  # pragma: no cover - non-Unix
            pass
    log.info("capture worker started: %s", ", ".join(r.venue for r in runners))
    try:
        if duration is None:
            await stop.wait()
        else:
            await asyncio.wait_for(stop.wait(), timeout=duration)
    except TimeoutError:
        pass
    finally:
        log.info("capture worker stopping")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for r in runners:
            await r.adapter.aclose()
