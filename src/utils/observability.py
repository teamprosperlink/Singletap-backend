"""
Comprehensive Observability Utilities for Vriddhi Matching Engine.

This module provides unified logging and tracing for:
- Match results and outcomes
- Database operations (Supabase, Qdrant)
- GPT/AI extractions
- External API calls
- Performance metrics

Usage:
    from src.utils.observability import obs

    # Log a match result
    obs.log_match_result(user_id, query, matches, latency_ms)

    # Trace a database operation
    with obs.trace_db_operation("supabase", "select", "service_listings") as span:
        result = supabase.table("service_listings").select("*").execute()
        span.set_attribute("rows_returned", len(result.data))

    # Log GPT extraction
    obs.log_gpt_extraction(query, extracted_json, tokens, latency_ms)
"""

import time
import json
from typing import Any, Dict, List, Optional, Union
from contextlib import contextmanager
from functools import wraps

from src.utils.logging import get_logger, LogEmoji
from src.utils.grafana import get_tracer, add_span_attributes, record_exception, is_grafana_enabled

# Module logger
_log = get_logger("observability")

# Module tracer
_tracer = None


def _get_tracer():
    """Lazy load tracer to avoid import issues."""
    global _tracer
    if _tracer is None:
        _tracer = get_tracer("vriddhi.observability")
    return _tracer


class ObservabilityManager:
    """
    Centralized observability manager for the Vriddhi Matching Engine.

    Provides unified logging and tracing for all operations.
    """

    def __init__(self):
        self.log = get_logger("vriddhi.obs")

    # =========================================================================
    # MATCH OPERATIONS
    # =========================================================================

    def log_match_request(
        self,
        user_id: str,
        query: str,
        intent: str = None,
        **extra
    ):
        """Log incoming match request."""
        self.log.info(
            "Match request received",
            emoji="search",
            user_id=user_id,
            query_length=len(query),
            query_preview=query[:100] + "..." if len(query) > 100 else query,
            intent=intent,
            **extra
        )

    def log_match_result(
        self,
        user_id: str,
        query: str,
        match_count: int,
        matched_user_ids: List[str] = None,
        matched_listing_ids: List[str] = None,
        latency_ms: float = None,
        **extra
    ):
        """Log match result with all details."""
        self.log.info(
            "Match completed",
            emoji="match",
            user_id=user_id,
            query_preview=query[:50] + "..." if len(query) > 50 else query,
            match_count=match_count,
            has_matches=match_count > 0,
            matched_user_ids=matched_user_ids[:5] if matched_user_ids else [],  # Limit to first 5
            matched_listing_ids=matched_listing_ids[:5] if matched_listing_ids else [],
            latency_ms=round(latency_ms, 2) if latency_ms else None,
            **extra
        )

    def log_no_match(
        self,
        user_id: str,
        query: str,
        reason: str = None,
        candidates_checked: int = 0,
        **extra
    ):
        """Log when no match is found."""
        self.log.info(
            "No match found",
            emoji="warning",
            user_id=user_id,
            query_preview=query[:50] + "..." if len(query) > 50 else query,
            reason=reason or "No candidates matched criteria",
            candidates_checked=candidates_checked,
            **extra
        )

    @contextmanager
    def trace_match_operation(self, operation: str, user_id: str = None, **attrs):
        """
        Trace a matching operation.

        Usage:
            with obs.trace_match_operation("boolean-matching", user_id="123") as span:
                result = perform_matching()
                span.set_attribute("matches_found", len(result))
        """
        tracer = _get_tracer()
        with tracer.start_as_current_span(f"match.{operation}") as span:
            add_span_attributes(span,
                operation=operation,
                user_id=user_id,
                **attrs
            )
            try:
                yield span
            except Exception as e:
                record_exception(span, e, f"Match operation failed: {operation}")
                raise

    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================

    def log_db_query(
        self,
        database: str,  # "supabase" or "qdrant"
        operation: str,  # "select", "insert", "update", "delete", "search"
        table: str,
        rows_affected: int = None,
        latency_ms: float = None,
        **extra
    ):
        """Log database query."""
        self.log.info(
            f"DB {operation}",
            emoji="db",
            database=database,
            operation=operation,
            table=table,
            rows_affected=rows_affected,
            latency_ms=round(latency_ms, 2) if latency_ms else None,
            **extra
        )

    def log_db_error(
        self,
        database: str,
        operation: str,
        table: str,
        error: str,
        **extra
    ):
        """Log database error."""
        self.log.error(
            f"DB {operation} failed",
            emoji="error",
            database=database,
            operation=operation,
            table=table,
            error=error,
            **extra
        )

    @contextmanager
    def trace_db_operation(
        self,
        database: str,
        operation: str,
        table: str,
        **attrs
    ):
        """
        Trace a database operation.

        Usage:
            with obs.trace_db_operation("supabase", "select", "service_listings") as span:
                result = supabase.table("service_listings").select("*").execute()
                span.set_attribute("rows_returned", len(result.data))
        """
        tracer = _get_tracer()
        span_name = f"db.{database}.{operation}"

        start_time = time.time()
        with tracer.start_as_current_span(span_name) as span:
            add_span_attributes(span,
                **{
                    "db.system": database,
                    "db.operation": operation,
                    "db.table": table,
                    **attrs
                }
            )
            try:
                yield span
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("db.latency_ms", round(latency_ms, 2))
            except Exception as e:
                record_exception(span, e, f"Database operation failed")
                self.log_db_error(database, operation, table, str(e))
                raise

    # =========================================================================
    # VECTOR SEARCH OPERATIONS
    # =========================================================================

    def log_vector_search(
        self,
        collection: str,
        query_vector_dim: int = None,
        results_count: int = None,
        top_score: float = None,
        latency_ms: float = None,
        filters: dict = None,
        **extra
    ):
        """Log vector search operation."""
        self.log.info(
            "Vector search",
            emoji="vector",
            collection=collection,
            query_vector_dim=query_vector_dim,
            results_count=results_count,
            top_score=round(top_score, 4) if top_score else None,
            latency_ms=round(latency_ms, 2) if latency_ms else None,
            filters=filters,
            **extra
        )

    @contextmanager
    def trace_vector_search(self, collection: str, **attrs):
        """Trace vector search operation."""
        tracer = _get_tracer()
        start_time = time.time()

        with tracer.start_as_current_span(f"vector.search.{collection}") as span:
            add_span_attributes(span,
                **{
                    "vector.collection": collection,
                    **attrs
                }
            )
            try:
                yield span
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("vector.latency_ms", round(latency_ms, 2))
            except Exception as e:
                record_exception(span, e, "Vector search failed")
                raise

    # =========================================================================
    # GPT/AI EXTRACTION OPERATIONS
    # =========================================================================

    def log_gpt_extraction(
        self,
        query: str,
        extracted_intent: str = None,
        extracted_json: dict = None,
        model: str = "gpt-4o",
        tokens_used: int = None,
        latency_ms: float = None,
        success: bool = True,
        error: str = None,
        **extra
    ):
        """Log GPT extraction operation."""
        if success:
            self.log.info(
                "GPT extraction complete",
                emoji="extract",
                query_length=len(query),
                query_preview=query[:50] + "..." if len(query) > 50 else query,
                extracted_intent=extracted_intent,
                model=model,
                tokens_used=tokens_used,
                latency_ms=round(latency_ms, 2) if latency_ms else None,
                **extra
            )
        else:
            self.log.error(
                "GPT extraction failed",
                emoji="error",
                query_length=len(query),
                model=model,
                error=error,
                latency_ms=round(latency_ms, 2) if latency_ms else None,
                **extra
            )

    @contextmanager
    def trace_gpt_extraction(self, query: str, model: str = "gpt-4o", **attrs):
        """Trace GPT extraction operation."""
        tracer = _get_tracer()
        start_time = time.time()

        with tracer.start_as_current_span("ai.gpt.extraction") as span:
            add_span_attributes(span,
                **{
                    "ai.model": model,
                    "ai.query_length": len(query),
                    **attrs
                }
            )
            try:
                yield span
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("ai.latency_ms", round(latency_ms, 2))
            except Exception as e:
                record_exception(span, e, "GPT extraction failed")
                raise

    # =========================================================================
    # CANONICALIZATION OPERATIONS
    # =========================================================================

    def log_canonicalization(
        self,
        input_fields: List[str] = None,
        resolved_fields: List[str] = None,
        latency_ms: float = None,
        **extra
    ):
        """Log canonicalization operation."""
        self.log.info(
            "Canonicalization complete",
            emoji="sync",
            input_fields=input_fields,
            resolved_fields=resolved_fields,
            latency_ms=round(latency_ms, 2) if latency_ms else None,
            **extra
        )

    @contextmanager
    def trace_canonicalization(self, **attrs):
        """Trace canonicalization operation."""
        tracer = _get_tracer()
        start_time = time.time()

        with tracer.start_as_current_span("pipeline.canonicalization") as span:
            add_span_attributes(span, **attrs)
            try:
                yield span
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("canonicalization.latency_ms", round(latency_ms, 2))
            except Exception as e:
                record_exception(span, e, "Canonicalization failed")
                raise

    # =========================================================================
    # EXTERNAL API OPERATIONS
    # =========================================================================

    def log_external_api(
        self,
        service: str,  # "wikidata", "babelnet", "openai", etc.
        operation: str,
        success: bool = True,
        latency_ms: float = None,
        error: str = None,
        **extra
    ):
        """Log external API call."""
        if success:
            self.log.info(
                f"External API: {service}",
                emoji="sync",
                service=service,
                operation=operation,
                success=True,
                latency_ms=round(latency_ms, 2) if latency_ms else None,
                **extra
            )
        else:
            self.log.warning(
                f"External API failed: {service}",
                emoji="warning",
                service=service,
                operation=operation,
                success=False,
                error=error,
                latency_ms=round(latency_ms, 2) if latency_ms else None,
                **extra
            )

    @contextmanager
    def trace_external_api(self, service: str, operation: str, **attrs):
        """Trace external API call."""
        tracer = _get_tracer()
        start_time = time.time()

        with tracer.start_as_current_span(f"external.{service}.{operation}") as span:
            add_span_attributes(span,
                **{
                    "external.service": service,
                    "external.operation": operation,
                    **attrs
                }
            )
            try:
                yield span
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("external.latency_ms", round(latency_ms, 2))
            except Exception as e:
                record_exception(span, e, f"External API failed: {service}")
                raise

    # =========================================================================
    # INGESTION OPERATIONS
    # =========================================================================

    def log_ingestion(
        self,
        user_id: str,
        listing_id: str,
        intent: str,
        table: str,
        latency_ms: float = None,
        **extra
    ):
        """Log listing ingestion."""
        self.log.info(
            "Listing ingested",
            emoji="store",
            user_id=user_id,
            listing_id=listing_id,
            intent=intent,
            table=table,
            latency_ms=round(latency_ms, 2) if latency_ms else None,
            **extra
        )

    @contextmanager
    def trace_ingestion(self, user_id: str, intent: str, **attrs):
        """Trace listing ingestion."""
        tracer = _get_tracer()
        start_time = time.time()

        with tracer.start_as_current_span("pipeline.ingestion") as span:
            add_span_attributes(span,
                **{
                    "ingestion.user_id": user_id,
                    "ingestion.intent": intent,
                    **attrs
                }
            )
            try:
                yield span
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("ingestion.latency_ms", round(latency_ms, 2))
            except Exception as e:
                record_exception(span, e, "Ingestion failed")
                raise

    # =========================================================================
    # BOOLEAN MATCHING OPERATIONS
    # =========================================================================

    def log_boolean_match(
        self,
        listing_a_id: str = None,
        listing_b_id: str = None,
        is_match: bool = False,
        match_reason: str = None,
        failed_fields: List[str] = None,
        latency_ms: float = None,
        **extra
    ):
        """Log boolean matching result."""
        if is_match:
            self.log.info(
                "Boolean match: SUCCESS",
                emoji="boolean",
                listing_a_id=listing_a_id,
                listing_b_id=listing_b_id,
                is_match=True,
                match_reason=match_reason,
                latency_ms=round(latency_ms, 2) if latency_ms else None,
                **extra
            )
        else:
            self.log.info(
                "Boolean match: FAIL",
                emoji="boolean",
                listing_a_id=listing_a_id,
                listing_b_id=listing_b_id,
                is_match=False,
                failed_fields=failed_fields,
                latency_ms=round(latency_ms, 2) if latency_ms else None,
                **extra
            )

    @contextmanager
    def trace_boolean_matching(self, **attrs):
        """Trace boolean matching operation."""
        tracer = _get_tracer()
        start_time = time.time()

        with tracer.start_as_current_span("match.boolean") as span:
            add_span_attributes(span, **attrs)
            try:
                yield span
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("boolean.latency_ms", round(latency_ms, 2))
            except Exception as e:
                record_exception(span, e, "Boolean matching failed")
                raise

    # =========================================================================
    # SEMANTIC MATCHING OPERATIONS
    # =========================================================================

    def log_semantic_match(
        self,
        candidate_value: str,
        required_value: str,
        is_match: bool,
        match_method: str = None,  # "exact", "wordnet", "wikidata", "embedding"
        similarity_score: float = None,
        **extra
    ):
        """Log semantic matching result."""
        self.log.debug(
            f"Semantic match: {'YES' if is_match else 'NO'}",
            emoji="semantic",
            candidate=candidate_value,
            required=required_value,
            is_match=is_match,
            method=match_method,
            similarity=round(similarity_score, 4) if similarity_score else None,
            **extra
        )

    # =========================================================================
    # FULL PIPELINE TRACING
    # =========================================================================

    @contextmanager
    def trace_full_pipeline(self, endpoint: str, user_id: str = None, **attrs):
        """
        Trace the full request pipeline.

        Usage:
            with obs.trace_full_pipeline("/search-and-match", user_id="123") as span:
                # ... full pipeline execution
                span.set_attribute("result.match_count", len(matches))
        """
        tracer = _get_tracer()
        start_time = time.time()

        with tracer.start_as_current_span(f"pipeline{endpoint}") as span:
            add_span_attributes(span,
                **{
                    "pipeline.endpoint": endpoint,
                    "pipeline.user_id": user_id,
                    **attrs
                }
            )
            try:
                yield span
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("pipeline.latency_ms", round(latency_ms, 2))
                span.set_attribute("pipeline.success", True)
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("pipeline.latency_ms", round(latency_ms, 2))
                span.set_attribute("pipeline.success", False)
                record_exception(span, e, f"Pipeline failed: {endpoint}")
                raise

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def timed(self, operation_name: str):
        """
        Decorator to time and trace a function.

        Usage:
            @obs.timed("process_listing")
            def process_listing(listing):
                ...
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                tracer = _get_tracer()
                start_time = time.time()

                with tracer.start_as_current_span(operation_name) as span:
                    add_span_attributes(span,
                        **{
                            "function.name": func.__name__,
                            "function.module": func.__module__,
                        }
                    )
                    try:
                        result = func(*args, **kwargs)
                        latency_ms = (time.time() - start_time) * 1000
                        span.set_attribute("function.latency_ms", round(latency_ms, 2))
                        span.set_attribute("function.success", True)
                        return result
                    except Exception as e:
                        latency_ms = (time.time() - start_time) * 1000
                        span.set_attribute("function.latency_ms", round(latency_ms, 2))
                        span.set_attribute("function.success", False)
                        record_exception(span, e)
                        raise

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                tracer = _get_tracer()
                start_time = time.time()

                with tracer.start_as_current_span(operation_name) as span:
                    add_span_attributes(span,
                        **{
                            "function.name": func.__name__,
                            "function.module": func.__module__,
                        }
                    )
                    try:
                        result = await func(*args, **kwargs)
                        latency_ms = (time.time() - start_time) * 1000
                        span.set_attribute("function.latency_ms", round(latency_ms, 2))
                        span.set_attribute("function.success", True)
                        return result
                    except Exception as e:
                        latency_ms = (time.time() - start_time) * 1000
                        span.set_attribute("function.latency_ms", round(latency_ms, 2))
                        span.set_attribute("function.success", False)
                        record_exception(span, e)
                        raise

            import asyncio
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return wrapper

        return decorator


# Global singleton instance
obs = ObservabilityManager()


# Convenience exports
log_match_result = obs.log_match_result
log_match_request = obs.log_match_request
log_db_query = obs.log_db_query
log_vector_search = obs.log_vector_search
log_gpt_extraction = obs.log_gpt_extraction
log_ingestion = obs.log_ingestion
log_boolean_match = obs.log_boolean_match
trace_match_operation = obs.trace_match_operation
trace_db_operation = obs.trace_db_operation
trace_vector_search = obs.trace_vector_search
trace_gpt_extraction = obs.trace_gpt_extraction
trace_full_pipeline = obs.trace_full_pipeline
timed = obs.timed
