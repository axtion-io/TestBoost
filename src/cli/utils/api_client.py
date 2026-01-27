"""HTTP API client for CLI commands."""

from typing import Any

import httpx

from src.cli.constants import API_BASE_URL, DEFAULT_TIMEOUT, Endpoints


class APIError(Exception):
    """API error with status code and details."""

    def __init__(self, status_code: int, message: str, details: dict[str, Any] | None = None):
        self.status_code = status_code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{status_code}] {message}")


class APIClient:
    """HTTP client for TestBoost API calls."""

    def __init__(self, base_url: str | None = None, timeout: int = DEFAULT_TIMEOUT):
        """Initialize API client.

        Args:
            base_url: API base URL (default: from environment or localhost:8000)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or API_BASE_URL
        self.timeout = timeout

    def _build_url(self, endpoint: str, **path_params: str) -> str:
        """Build full URL with path parameters.

        Args:
            endpoint: Endpoint template (e.g., "/sessions/{session_id}")
            **path_params: Path parameter values

        Returns:
            Full URL with parameters substituted
        """
        path = endpoint.format(**path_params) if path_params else endpoint
        return f"{self.base_url}{path}"

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle API response and raise appropriate errors.

        Args:
            response: httpx Response object

        Returns:
            Response JSON data

        Raises:
            APIError: If response indicates an error
        """
        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("detail", str(error_data))
            except Exception:
                message = response.text or f"HTTP {response.status_code}"

            # Map common error codes to user-friendly messages
            if response.status_code == 401:
                message = "Authentication required. Check API key configuration."
            elif response.status_code == 404:
                message = f"Resource not found: {message}"
            elif response.status_code == 409:
                message = f"Conflict: {message}"
            elif response.status_code == 422:
                message = f"Validation error: {message}"
            elif response.status_code == 429:
                message = "Rate limit exceeded. Please wait and retry."
            elif response.status_code == 500:
                message = f"Server error: {message}"
            elif response.status_code == 502:
                message = "API server unavailable (bad gateway)."
            elif response.status_code == 503:
                message = "API server temporarily unavailable."

            raise APIError(response.status_code, message)

        if response.status_code == 204:
            return {}

        try:
            result: dict[str, Any] = response.json()
            return result
        except Exception:
            return {"raw": response.text}

    def get(
        self, endpoint: str, params: dict[str, Any] | None = None, **path_params: str
    ) -> dict[str, Any]:
        """Make GET request.

        Args:
            endpoint: API endpoint template
            params: Query parameters
            **path_params: Path parameter values

        Returns:
            Response data
        """
        url = self._build_url(endpoint, **path_params)
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, params=params)
            return self._handle_response(response)

    def post(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        **path_params: str,
    ) -> dict[str, Any]:
        """Make POST request.

        Args:
            endpoint: API endpoint template
            data: Request body (JSON)
            params: Query parameters
            **path_params: Path parameter values

        Returns:
            Response data
        """
        url = self._build_url(endpoint, **path_params)
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=data or {}, params=params)
            return self._handle_response(response)

    def patch(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        **path_params: str,
    ) -> dict[str, Any]:
        """Make PATCH request.

        Args:
            endpoint: API endpoint template
            data: Request body (JSON)
            **path_params: Path parameter values

        Returns:
            Response data
        """
        url = self._build_url(endpoint, **path_params)
        with httpx.Client(timeout=self.timeout) as client:
            response = client.patch(url, json=data or {})
            return self._handle_response(response)

    def delete(self, endpoint: str, **path_params: str) -> dict[str, Any]:
        """Make DELETE request.

        Args:
            endpoint: API endpoint template
            **path_params: Path parameter values

        Returns:
            Response data (empty for 204)
        """
        url = self._build_url(endpoint, **path_params)
        with httpx.Client(timeout=self.timeout) as client:
            response = client.delete(url)
            return self._handle_response(response)

    # Convenience methods for common operations

    def get_session(self, session_id: str) -> dict[str, Any]:
        """Get session by ID."""
        return self.get(Endpoints.SESSION, session_id=session_id)

    def list_sessions(
        self,
        status: str | None = None,
        session_type: str | None = None,
        limit: int = 20,
        page: int = 1,
    ) -> dict[str, Any]:
        """List sessions with optional filters."""
        params: dict[str, Any] = {"per_page": limit, "page": page}
        if status:
            params["status"] = status
        if session_type:
            params["session_type"] = session_type
        return self.get(Endpoints.SESSIONS, params=params)

    def get_steps(self, session_id: str) -> dict[str, Any]:
        """Get all steps for a session."""
        return self.get(Endpoints.SESSION_STEPS, session_id=session_id)

    def execute_step(
        self, session_id: str, step_code: str, inputs: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a specific step.

        Args:
            session_id: Session UUID
            step_code: Step code to execute
            inputs: Optional input data for the step
            run_workflow: If True, execute the actual workflow (default: True)
            run_in_background: If True and run_workflow=True, run in background task
        """
        return self.post(
            Endpoints.SESSION_STEP_EXECUTE,
            data={"inputs": inputs or {}},
            session_id=session_id,
            step_code=step_code,
        )

    def get_artifacts(
        self, session_id: str, artifact_type: str | None = None
    ) -> dict[str, Any]:
        """Get artifacts for a session."""
        params = {"artifact_type": artifact_type} if artifact_type else None
        return self.get(Endpoints.SESSION_ARTIFACTS, params=params, session_id=session_id)

    def pause_session(self, session_id: str, reason: str | None = None) -> dict[str, Any]:
        """Pause a running session."""
        return self.post(
            Endpoints.SESSION_PAUSE,
            data={"reason": reason} if reason else None,
            session_id=session_id,
        )

    def resume_session(
        self, session_id: str, checkpoint_id: str | None = None
    ) -> dict[str, Any]:
        """Resume a paused session."""
        return self.post(
            Endpoints.SESSION_RESUME,
            data={"checkpoint_id": checkpoint_id} if checkpoint_id else None,
            session_id=session_id,
        )

    def cancel_maintenance(self, session_id: str) -> dict[str, Any]:
        """Cancel a maintenance session."""
        return self.delete(Endpoints.MAINTENANCE_MAVEN_STATUS, session_id=session_id)
