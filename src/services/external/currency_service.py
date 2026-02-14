"""
Currency exchange rate service using frankfurter.app.

frankfurter.app is free, requires no API key, and uses European Central Bank data.
Supports 30+ currencies including INR, USD, EUR, GBP, JPY, AED, etc.
Rates update once per business day.

Usage:
    service = get_currency_service()
    rate = service.get_rate("INR", "USD")    # 0.012
    usd = service.convert(50000, "INR")      # 600.0
"""

import time
import requests
from typing import Dict, Optional, Set
from threading import Lock


class CurrencyService:
    """
    Live currency exchange rate service with in-memory caching.

    Caching: In-memory with 6-hour TTL (rates change once/business day).
    Thread-safe via Lock.
    Graceful degradation: returns None on API failure or unknown currency.
    """

    BASE_URL = "https://api.frankfurter.app"
    DEFAULT_CACHE_TTL = 6 * 60 * 60  # 6 hours

    def __init__(self, cache_ttl_seconds: int = DEFAULT_CACHE_TTL):
        self._cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Dict] = {}
        self._supported_currencies: Optional[Set[str]] = None
        self._lock = Lock()
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Vriddhi-MatchingEngine/2.0"
        })

    def get_rate(self, from_currency: str, to_currency: str = "USD") -> Optional[float]:
        """
        Get exchange rate from one currency to another.

        Args:
            from_currency: Source currency code (e.g., "INR", "EUR")
            to_currency: Target currency code (default: "USD")

        Returns:
            Exchange rate as float, or None if unavailable.
        """
        from_currency = from_currency.upper().strip()
        to_currency = to_currency.upper().strip()

        if from_currency == to_currency:
            return 1.0

        rates = self._get_cached_rates(from_currency)
        if rates is None:
            rates = self._fetch_rates(from_currency)
            if rates is None:
                return None
            self._set_cached_rates(from_currency, rates)

        return rates.get(to_currency)

    def convert(self, amount: float, from_currency: str, to_currency: str = "USD") -> Optional[float]:
        """
        Convert amount from one currency to another.

        Args:
            amount: Numeric amount to convert
            from_currency: Source currency code
            to_currency: Target currency code

        Returns:
            Converted amount, or None if conversion fails.
        """
        rate = self.get_rate(from_currency, to_currency)
        if rate is None:
            return None
        return amount * rate

    def get_supported_currencies(self) -> Set[str]:
        """
        Get the set of all supported currency codes (dynamic, API-backed).

        Fetches from frankfurter.app /currencies endpoint on first call,
        then caches permanently (currency list rarely changes).

        Returns:
            Set of uppercase currency codes (e.g., {"USD", "EUR", "INR", ...})
            Returns empty set if API is unavailable.
        """
        if self._supported_currencies is not None:
            return self._supported_currencies

        currencies = self._fetch_supported_currencies()
        if currencies:
            self._supported_currencies = currencies
        else:
            # API failed — return empty set, will retry on next call
            return set()

        return self._supported_currencies

    def is_currency_code(self, code: str) -> bool:
        """
        Check if a string is a valid currency code (dynamic, API-backed).

        Args:
            code: String to check (e.g., "INR", "USD", "XYZ")

        Returns:
            True if the code is a recognized currency code.
        """
        supported = self.get_supported_currencies()
        if not supported:
            # API unavailable — fall back to checking if the code
            # looks like a 3-letter uppercase string (ISO 4217 format)
            code = code.upper().strip()
            return len(code) == 3 and code.isalpha()
        return code.upper().strip() in supported

    def _fetch_supported_currencies(self) -> Optional[Set[str]]:
        """
        Fetch list of supported currencies from frankfurter.app.

        API: GET https://api.frankfurter.app/currencies
        Response: {"AUD": "Australian Dollar", "BGN": "Bulgarian Lev", ...}
        """
        try:
            url = f"{self.BASE_URL}/currencies"
            response = self._session.get(url, timeout=5)

            if response.status_code != 200:
                print(f"Currency API error fetching currency list: {response.status_code}")
                return None

            data = response.json()
            return set(data.keys())

        except requests.exceptions.Timeout:
            print("Currency API timeout fetching currency list")
            return None
        except requests.exceptions.ConnectionError:
            print("Currency API connection error fetching currency list")
            return None
        except Exception as e:
            print(f"Currency API unexpected error fetching currency list: {e}")
            return None

    def _fetch_rates(self, base_currency: str) -> Optional[Dict[str, float]]:
        """
        Fetch latest rates from frankfurter.app.

        API: GET https://api.frankfurter.app/latest?from={base}
        Response: {"base": "USD", "date": "2026-02-04", "rates": {"EUR": 0.92, ...}}
        """
        try:
            url = f"{self.BASE_URL}/latest?from={base_currency}"
            response = self._session.get(url, timeout=5)

            if response.status_code != 200:
                print(f"Currency API error: {response.status_code} for {base_currency}")
                return None

            data = response.json()
            return data.get("rates", {})

        except requests.exceptions.Timeout:
            print(f"Currency API timeout for {base_currency}")
            return None
        except requests.exceptions.ConnectionError:
            print(f"Currency API connection error for {base_currency}")
            return None
        except Exception as e:
            print(f"Currency API unexpected error for {base_currency}: {e}")
            return None

    def _get_cached_rates(self, base_currency: str) -> Optional[Dict[str, float]]:
        """Get rates from cache if within TTL."""
        with self._lock:
            entry = self._cache.get(base_currency)
            if entry and (time.time() - entry["fetched_at"]) < self._cache_ttl:
                return entry["rates"]
            return None

    def _set_cached_rates(self, base_currency: str, rates: Dict[str, float]) -> None:
        """Store rates in cache with current timestamp."""
        with self._lock:
            self._cache[base_currency] = {
                "rates": rates,
                "fetched_at": time.time()
            }


# Global singleton
_currency_service: Optional[CurrencyService] = None


def get_currency_service() -> CurrencyService:
    """Get singleton CurrencyService instance."""
    global _currency_service
    if _currency_service is None:
        _currency_service = CurrencyService()
    return _currency_service
