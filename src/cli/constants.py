"""CLI constants and API endpoint definitions."""

import os

# API Configuration
API_BASE_URL = os.getenv("TESTBOOST_API_URL", "http://localhost:8000")

# API Endpoints
class Endpoints:
    """API endpoint paths."""

    # Health
    HEALTH = "/health"

    # Sessions (v2 API)
    SESSIONS = "/api/v2/sessions"
    SESSION = "/api/v2/sessions/{session_id}"
    SESSION_STEPS = "/api/v2/sessions/{session_id}/steps"
    SESSION_STEP = "/api/v2/sessions/{session_id}/steps/{step_code}"
    SESSION_STEP_EXECUTE = "/api/v2/sessions/{session_id}/steps/{step_code}/execute"
    SESSION_ARTIFACTS = "/api/v2/sessions/{session_id}/artifacts"
    SESSION_PAUSE = "/api/v2/sessions/{session_id}/pause"
    SESSION_RESUME = "/api/v2/sessions/{session_id}/resume"

    # TestBoost workflows
    MAINTENANCE_MAVEN = "/api/testboost/maintenance/maven"
    MAINTENANCE_MAVEN_STATUS = "/api/testboost/maintenance/maven/{session_id}"

    # Audit (to be implemented)
    AUDIT_SCAN = "/api/audit/scan"
    AUDIT_REPORT = "/api/audit/report/{session_id}"
    AUDIT_REPORT_HTML = "/api/audit/report/{session_id}/html"

    # Impact Analysis (to be implemented)
    TESTS_IMPACT = "/api/tests/impact"


# Default timeouts (seconds)
DEFAULT_TIMEOUT = 30
LONG_TIMEOUT = 120

# Pagination defaults
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
