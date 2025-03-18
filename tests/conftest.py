"""Common pytest fixtures for FAMP tests."""

import os
import pytest
import tempfile
from pathlib import Path

from famp.core.account import FacebookAccount
from famp.core.config import Settings


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def test_settings(tmp_dir):
    """Create test settings."""
    settings = Settings()
    settings.data_dir = str(tmp_dir)
    settings.log_level = "DEBUG"
    settings.log_file = None  # Log to console only for tests
    return settings


@pytest.fixture
def test_account():
    """Create a test Facebook account."""
    return FacebookAccount(
        account_id="test123",
        email="test@example.com",
        password="password123",
        user_agent="Mozilla/5.0 Test User Agent",
        proxy=None,
        two_factor_secret=None,
        notes="Test account for unit tests",
        active=True
    )


@pytest.fixture
def test_account_with_proxy():
    """Create a test Facebook account with proxy."""
    return FacebookAccount(
        account_id="proxy_test",
        email="proxy_test@example.com",
        password="proxy_password",
        user_agent="Mozilla/5.0 Proxy Test Agent",
        proxy="socks5://127.0.0.1:9050",
        two_factor_secret="ABCDEF123456",
        notes="Test account with proxy settings",
        active=True
    )