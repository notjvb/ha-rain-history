"""Open-Meteo client and rain totals. No Home Assistant imports, so it can be tested on its own."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import aiohttp

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# Archive of past forecasts; reaches back years, unlike past_days on FORECAST_URL (max 92).
HISTORICAL_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"

# Days in the "recent" window, today included. Covers today / 3 / 7 / 30 day totals.
RECENT_DAYS = 30
# Always keep at least this much history, so "last rain" can see back past a dry season.
LAST_RAIN_LOOKBACK_DAYS = 365

# Open-Meteo's free API sheds load with 429/5xx, mostly around the top of the hour.
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
RETRY_DELAYS = (5, 20, 60)  # seconds before each retry


class OpenMeteoError(Exception):
    """Open-Meteo request failed."""

    def __init__(self, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.transient = transient


@dataclass
class RainTotals:
    """Rain totals in the client's unit. Year totals are None when history couldn't be fetched.

    last_rain is the latest day with at least the rain threshold; None if there was none
    in the lookback window (or history couldn't be fetched and none was in recent days).
    """

    today: float
    last_3_days: float
    last_7_days: float
    last_30_days: float
    this_rain_year: float | None
    last_rain_year: float | None
    rain_year_start: date
    as_of: date
    last_rain: date | None
    last_rain_amount: float | None
    last_rain_searched_since: date

    @property
    def days_since_rain(self) -> int | None:
        return None if self.last_rain is None else (self.as_of - self.last_rain).days


def rain_year_start(today: date, start_month: int) -> date:
    """First day of the rain year containing `today`."""
    year = today.year if today.month >= start_month else today.year - 1
    return date(year, start_month, 1)


def _parse_daily(payload: dict[str, Any]) -> dict[date, float]:
    try:
        daily = payload["daily"]
        return {
            date.fromisoformat(day): float(mm or 0)
            for day, mm in zip(daily["time"], daily["precipitation_sum"], strict=True)
        }
    except (KeyError, TypeError, ValueError) as err:
        raise OpenMeteoError(f"Unexpected response: {err}") from err


class OpenMeteoRainClient:
    """Fetches daily precipitation and turns it into rain totals."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        latitude: float,
        longitude: float,
        inches: bool,
    ) -> None:
        self._session = session
        self._unit = "inch" if inches else "mm"
        self._latitude = latitude
        self._longitude = longitude
        # Historical days only change once a day, so keep them between hourly updates.
        self._history_range: tuple[date, date] | None = None
        self._history: dict[date, float] = {}
        # Every day seen so far, so a failed history refetch can fall back on it.
        self._known_days: dict[date, float] = {}

    async def _get_daily(self, url: str, **params: Any) -> dict[date, float]:
        for delay in (*RETRY_DELAYS, None):
            try:
                return await self._get_daily_once(url, **params)
            except OpenMeteoError as err:
                if not err.transient or delay is None:
                    raise
            await asyncio.sleep(delay)
        raise AssertionError("unreachable")

    async def _get_daily_once(self, url: str, **params: Any) -> dict[date, float]:
        query = {
            "latitude": self._latitude,
            "longitude": self._longitude,
            "daily": "precipitation_sum",
            "timezone": "auto",
            "precipitation_unit": self._unit,
            **params,
        }
        try:
            async with self._session.get(
                url, params=query, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                payload = await resp.json(content_type=None)
                if resp.status != 200:
                    reason = payload.get("reason") if isinstance(payload, dict) else None
                    raise OpenMeteoError(
                        f"HTTP {resp.status}: {reason or 'error'}",
                        transient=resp.status in RETRY_STATUSES,
                    )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise OpenMeteoError(str(err) or type(err).__name__, transient=True) from err
        except ValueError as err:
            # Non-JSON body, e.g. an HTML error page from a proxy.
            raise OpenMeteoError(f"Bad response: {err}", transient=True) from err
        return _parse_daily(payload)

    async def async_get_totals(
        self, start_month: int, include_last_rain_year: bool, rain_threshold: float
    ) -> RainTotals:
        """Totals for the location's today. rain_threshold is in the client's unit."""
        # Today's value includes rain still forecast for the rest of the day.
        recent = await self._get_daily(
            FORECAST_URL, past_days=RECENT_DAYS - 1, forecast_days=1
        )
        # Use the location's own calendar (timezone=auto), not HA's clock.
        today = max(recent)
        ry_start = rain_year_start(today, start_month)
        last_ry_start = ry_start.replace(year=ry_start.year - 1)

        history_ok = True
        history_start = min(
            last_ry_start if include_last_rain_year else ry_start,
            today - timedelta(days=LAST_RAIN_LOOKBACK_DAYS),
        )
        history_end = today - timedelta(days=RECENT_DAYS)
        if history_start <= history_end and self._history_range != (
            history_start,
            history_end,
        ):
            try:
                self._history = await self._get_daily(
                    HISTORICAL_URL,
                    start_date=history_start.isoformat(),
                    end_date=history_end.isoformat(),
                )
                self._history_range = (history_start, history_end)
            except OpenMeteoError:
                # The range moves by a day each day; earlier fetches usually cover it.
                needed = history_start
                while needed <= history_end and needed in self._known_days:
                    needed += timedelta(days=1)
                history_ok = needed > history_end
                if history_ok:
                    self._history = {
                        d: mm
                        for d, mm in self._known_days.items()
                        if history_start <= d <= history_end
                    }
                    self._history_range = None  # still try a fresh fetch next update

        days = {**self._history, **recent}
        self._known_days = {
            d: mm for d, mm in {**self._known_days, **days}.items() if d >= history_start
        }

        def total(first: date, last: date) -> float:
            return round(sum(mm for d, mm in days.items() if first <= d <= last), 2)

        def last_n(n: int) -> float:
            return total(today - timedelta(days=n - 1), today)

        # Today counts once its total (including rain still forecast) reaches the threshold,
        # same as the "today" sensor. Search every day seen, so a failed history refetch
        # doesn't leave a gap between stale history and the recent window.
        seen = self._known_days
        last_rain = max((d for d, mm in seen.items() if mm >= rain_threshold), default=None)

        return RainTotals(
            today=last_n(1),
            last_3_days=last_n(3),
            last_7_days=last_n(7),
            last_30_days=last_n(30),
            this_rain_year=total(ry_start, today) if history_ok else None,
            last_rain_year=(
                total(last_ry_start, ry_start - timedelta(days=1))
                if history_ok and include_last_rain_year
                else None
            ),
            rain_year_start=ry_start,
            as_of=today,
            last_rain=last_rain,
            last_rain_amount=None if last_rain is None else round(seen[last_rain], 2),
            last_rain_searched_since=min(seen),
        )
