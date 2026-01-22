"""Prometheus metrics endpoint for observability (CHK042).

Exposes application metrics in Prometheus format for monitoring.
"""

from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from src.lib.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["metrics"])


# In-memory metrics storage (simple implementation)
# For production, use prometheus_client library
class MetricsCollector:
    """Simple metrics collector for application metrics."""

    def __init__(self) -> None:
        """Initialize metrics storage."""
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._labels: dict[str, dict[str, str]] = {}

    def inc_counter(self, name: str, value: int = 1, labels: dict[str, str] | None = None) -> None:
        """Increment a counter metric."""
        key = self._make_key(name, labels)
        self._counters[key] += value
        if labels:
            self._labels[key] = labels

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge metric value."""
        key = self._make_key(name, labels)
        self._gauges[key] = value
        if labels:
            self._labels[key] = labels

    def observe_histogram(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Record a histogram observation."""
        key = self._make_key(name, labels)
        self._histograms[key].append(value)
        if labels:
            self._labels[key] = labels

    def _make_key(self, name: str, labels: dict[str, str] | None) -> str:
        """Create a unique key from name and labels."""
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def format_prometheus(self) -> str:
        """Format metrics in Prometheus exposition format."""
        lines: list[str] = []

        # Format counters
        for counter_key, counter_value in sorted(self._counters.items()):
            name = counter_key.split("{")[0] if "{" in counter_key else counter_key
            if not any(line.startswith(f"# TYPE {name}") for line in lines):
                lines.append(f"# TYPE {name} counter")
            lines.append(f"{counter_key} {counter_value}")

        # Format gauges
        for gauge_key, gauge_value in sorted(self._gauges.items()):
            name = gauge_key.split("{")[0] if "{" in gauge_key else gauge_key
            if not any(line.startswith(f"# TYPE {name}") for line in lines):
                lines.append(f"# TYPE {name} gauge")
            lines.append(f"{gauge_key} {gauge_value}")

        # Format histograms (simplified - just expose sum and count)
        histogram_names = set()
        for key, values in sorted(self._histograms.items()):
            # Parse name and labels: "metric_name{label1=\"val1\"}" -> ("metric_name", "{label1=\"val1\"}")
            if "{" in key:
                name, labels = key.split("{", 1)
                labels = "{" + labels
            else:
                name = key
                labels = ""

            if name not in histogram_names:
                lines.append(f"# TYPE {name} histogram")
                histogram_names.add(name)

            if values:
                total = sum(values)
                count = len(values)
                # Correct Prometheus format: metric_name_sum{labels} value
                sum_key = f"{name}_sum{labels}"
                count_key = f"{name}_count{labels}"
                lines.append(f"{sum_key} {total}")
                lines.append(f"{count_key} {count}")

        return "\n".join(lines) + "\n" if lines else ""


# Global metrics instance
metrics = MetricsCollector()


def record_workflow_duration(
    workflow_type: str, duration_seconds: float, status: str = "success"
) -> None:
    """Record workflow execution duration."""
    metrics.observe_histogram(
        "testboost_workflow_duration_seconds",
        duration_seconds,
        labels={"workflow_type": workflow_type},
    )
    metrics.inc_counter(
        "testboost_workflow_total",
        labels={"workflow_type": workflow_type, "status": status},
    )


def record_llm_call(provider: str, model: str, success: bool = True) -> None:
    """Record an LLM API call."""
    metrics.inc_counter(
        "testboost_llm_calls_total",
        labels={"provider": provider, "model": model, "status": "success" if success else "error"},
    )
    if not success:
        metrics.inc_counter(
            "testboost_llm_errors_total",
            labels={"provider": provider, "error_type": "api_error"},
        )


def record_llm_rate_limit(provider: str) -> None:
    """Record an LLM rate limit error."""
    metrics.inc_counter(
        "testboost_llm_rate_limit_total",
        labels={"provider": provider},
    )
    metrics.inc_counter(
        "testboost_llm_errors_total",
        labels={"provider": provider, "error_type": "rate_limit"},
    )


def record_llm_duration(provider: str, duration_seconds: float) -> None:
    """Record LLM request duration."""
    metrics.observe_histogram(
        "testboost_llm_request_duration_seconds",
        duration_seconds,
        labels={"provider": provider},
    )


def set_active_sessions(count: int) -> None:
    """Set the number of active sessions."""
    metrics.set_gauge("testboost_active_sessions", float(count))


def set_db_connection_pool(active: int, max_size: int) -> None:
    """Set database connection pool metrics."""
    metrics.set_gauge("testboost_db_connection_pool_size", float(active))
    metrics.set_gauge("testboost_db_connection_pool_max", float(max_size))


def record_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    """Record an HTTP request."""
    metrics.inc_counter(
        "testboost_http_requests_total",
        labels={"method": method, "path": path, "status": str(status_code)},
    )
    metrics.observe_histogram(
        "testboost_http_request_duration_seconds",
        duration_seconds,
        labels={"method": method, "path": path},
    )


@router.get("/metrics", response_class=PlainTextResponse, response_model=None)
async def get_metrics() -> str:
    """
    Expose Prometheus metrics.

    Returns metrics in Prometheus exposition format for scraping.

    Returns:
        Plain text metrics in Prometheus format
    """
    # Initialize default metrics for Grafana dashboard visibility
    metrics.set_gauge("app_info", 1.0, labels={"version": "0.1.0"})

    # Initialize gauges with defaults if not set
    if "testboost_active_sessions" not in str(metrics._gauges):
        metrics.set_gauge("testboost_active_sessions", 0.0)
    if "testboost_db_connection_pool_size" not in str(metrics._gauges):
        metrics.set_gauge("testboost_db_connection_pool_size", 5.0)
        metrics.set_gauge("testboost_db_connection_pool_max", 20.0)

    return metrics.format_prometheus()


@router.get("/metrics/json")
async def get_metrics_json() -> dict[str, Any]:
    """
    Get metrics in JSON format for debugging.

    Returns:
        Dictionary with all metrics
    """
    return {
        "counters": dict(metrics._counters),
        "gauges": dict(metrics._gauges),
        "histograms": {k: {"count": len(v), "sum": sum(v)} for k, v in metrics._histograms.items()},
        "timestamp": datetime.utcnow().isoformat(),
    }


__all__ = [
    "router",
    "metrics",
    "record_workflow_duration",
    "record_llm_call",
    "record_llm_rate_limit",
    "record_llm_duration",
    "set_active_sessions",
    "set_db_connection_pool",
    "record_request",
]
