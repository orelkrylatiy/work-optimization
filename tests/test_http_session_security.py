"""Regression tests for secure HTTP session defaults."""

from hh_applicant_tool.main import HHApplicantTool


def test_http_session_verifies_tls_by_default() -> None:
    tool = object.__new__(HHApplicantTool)

    session = tool._create_http_session({}, log_label="test")

    assert session.verify is True
