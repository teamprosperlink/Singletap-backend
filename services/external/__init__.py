"""
External API wrappers for canonicalization services.
"""

from .wordnet_wrapper import WordNetClient, get_wordnet_client
from .babelnet_wrapper import BabelNetClient, get_babelnet_client
from .wikidata_wrapper import WikidataClient, get_wikidata_client
from .quantulum_wrapper import extract_quantities
from .pint_wrapper import normalize_unit, normalize_to_base, are_compatible
from .currency_service import CurrencyService, get_currency_service
from .geocoding_service import GeocodingService, get_geocoding_service
from .datamuse_wrapper import DatamuseClient, get_datamuse_client
from .wordsapi_wrapper import WordsAPIClient, get_wordsapi_client

__all__ = [
    "WordNetClient",
    "get_wordnet_client",
    "BabelNetClient",
    "get_babelnet_client",
    "WikidataClient",
    "get_wikidata_client",
    "DatamuseClient",
    "get_datamuse_client",
    "WordsAPIClient",
    "get_wordsapi_client",
    "extract_quantities",
    "normalize_unit",
    "normalize_to_base",
    "are_compatible",
    "CurrencyService",
    "get_currency_service",
    "GeocodingService",
    "get_geocoding_service",
]
