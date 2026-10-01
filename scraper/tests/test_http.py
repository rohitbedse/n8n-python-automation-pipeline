"""Tests for scraper/pipeline/http.py"""
import pytest
import json
from unittest.mock import Mock, patch
from scraper.pipeline.http import (
    fetch_json_with_retry,
    fetch_html_with_retry,
    fetch_with_retry,
    FetchResult,
)
import requests


def create_mock_response(status_code=200, json_data=None, text=None, headers=None, reason="OK"):
    """Create a properly configured mock response."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.reason = reason
    mock_response.headers = headers or {}
    
    if text is not None:
        mock_response.text = text
    elif json_data is not None:
        mock_response.text = json.dumps(json_data)
    else:
        mock_response.text = ""
    
    if json_data is not None:
        mock_response.json.return_value = json_data
    
    mock_response.raise_for_status = Mock()
    if status_code >= 400:
        mock_response.raise_for_status.side_effect = requests.HTTPError(f"{status_code} {reason}")
    else:
        mock_response.raise_for_status = Mock()
    
    return mock_response


class TestFetchJsonWithRetry:
    @patch("scraper.pipeline.http.requests.Session")
    def test_successful_fetch(self, mock_session_class):
        mock_response = create_mock_response(
            status_code=200,
            json_data={"data": "test"},
            headers={"Content-Type": "application/json"}
        )
        
        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session.default_timeout = 30
        mock_session_class.return_value = mock_session
        
        session = mock_session_class()
        result = fetch_json_with_retry(session, "GET", "https://example.com/api")
        
        assert result.success
        assert result.data == {"data": "test"}
        assert result.error is None

    @patch("scraper.pipeline.http.requests.Session")
    def test_http_error_retry(self, mock_session_class):
        mock_response = create_mock_response(
            status_code=500,
            reason="Internal Server Error"
        )
        
        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session.default_timeout = 30
        mock_session_class.return_value = mock_session
        
        session = mock_session_class()
        result = fetch_json_with_retry(session, "GET", "https://example.com/api", max_retries=2)
        
        assert not result.success
        assert "500" in result.error or "Internal Server Error" in result.error

    @patch("scraper.pipeline.http.requests.Session")
    def test_404_no_retry(self, mock_session_class):
        mock_response = create_mock_response(
            status_code=404,
            reason="Not Found"
        )
        
        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session.default_timeout = 30
        mock_session_class.return_value = mock_session
        
        session = mock_session_class()
        result = fetch_json_with_retry(session, "GET", "https://example.com/api", max_retries=3)
        
        assert not result.success


class TestFetchHtmlWithRetry:
    @patch("scraper.pipeline.http.requests.Session")
    def test_successful_html_fetch(self, mock_session_class):
        mock_response = create_mock_response(
            status_code=200,
            text="<html><body>Test</body></html>",
            headers={"Content-Type": "text/html"}
        )
        
        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session.default_timeout = 30
        mock_session_class.return_value = mock_session
        
        session = mock_session_class()
        result = fetch_html_with_retry(session, "https://example.com/page")
        
        assert result.success
        assert "Test" in result.data

    @patch("scraper.pipeline.http.requests.Session")
    def test_timeout_handling(self, mock_session_class):
        mock_session = Mock()
        mock_session.request.side_effect = requests.Timeout("Connection timed out")
        mock_session.default_timeout = 30
        mock_session_class.return_value = mock_session
        
        session = mock_session_class()
        result = fetch_html_with_retry(session, "https://example.com/page", max_retries=2)
        
        assert not result.success
        assert "timeout" in result.error.lower() or "timed out" in result.error.lower()