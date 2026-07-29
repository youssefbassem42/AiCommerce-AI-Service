"""Tests for the AuditLog domain entity."""
import pytest

from app.domain.auth.entities.audit_log import AuditLog


class TestAuditLogEntity:
    """Purpose: Validate AuditLog entity creation and default values."""

    def test_create_audit_log(self):
        """Preconditions: Valid parameters. Input: All required fields. Execution: Create entity. Expected: Entity with correct values."""
        log = AuditLog(
            id="log-1",
            action="user:login",
            resource_type="session",
            outcome="success",
        )
        assert log.id == "log-1"
        assert log.action == "user:login"
        assert log.resource_type == "session"
        assert log.outcome == "success"
        assert log.actor_type == "user"
        assert log.details == {}
        assert log.timestamp is not None

    def test_audit_log_with_all_fields(self):
        """Preconditions: Full parameters. Input: All fields. Execution: Create entity. Expected: All values set."""
        log = AuditLog(
            id="log-2",
            action="api_key:create",
            actor_id="user-1",
            actor_type="user",
            resource_type="api_key",
            resource_id="key-1",
            tenant_id="store-1",
            details={"key_name": "test"},
            ip_address="192.168.1.1",
            user_agent="curl/7.0",
            outcome="success",
        )
        assert log.actor_id == "user-1"
        assert log.resource_id == "key-1"
        assert log.tenant_id == "store-1"
        assert log.details == {"key_name": "test"}
        assert log.ip_address == "192.168.1.1"
        assert log.user_agent == "curl/7.0"

    def test_audit_log_failure_outcome(self):
        """Preconditions: Failure outcome. Input: outcome=failure with reason. Execution: Create entity. Expected: Failure tracked."""
        log = AuditLog(
            id="log-3",
            action="user:login",
            resource_type="session",
            outcome="failure",
            failure_reason="Invalid credentials",
        )
        assert log.outcome == "failure"
        assert log.failure_reason == "Invalid credentials"

    def test_audit_log_missing_optional_fields(self):
        """Preconditions: Only required fields. Input: Minimal fields. Execution: Create entity. Expected: Defaults for optionals."""
        log = AuditLog(
            id="log-4",
            action="system:startup",
            resource_type="service",
            outcome="success",
        )
        assert log.actor_id is None
        assert log.tenant_id is None
        assert log.ip_address is None
        assert log.failure_reason is None
