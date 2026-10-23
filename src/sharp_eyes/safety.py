"""Live-trading safety guard.

Every code path that could ever submit, amend or cancel a real order must call
:func:`assert_live_orders_allowed` first. In this release it always raises.
"""

from __future__ import annotations

from sharp_eyes.config import AppConfig


class LiveTradingDisabledError(RuntimeError):
    """Raised whenever something attempts a live venue order."""


def assert_live_orders_allowed(config: AppConfig) -> None:
    """Refuse live orders unconditionally in the initial release.

    ``AppConfig`` validation already rejects ``live_orders_enabled: true``; this
    second check exists so the guard still holds if a config object is built
    some other way (for example ``model_construct``).
    """
    raise LiveTradingDisabledError(
        "live order submission is disabled "
        f"(mode={config.execution.mode}, live_orders_enabled="
        f"{config.execution.live_orders_enabled}); paper mode only"
    )
