"""Tests for browser manager functionality."""

import asyncio
import pytest
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from famp.core.browser import BrowserManager
from famp.core.account import FacebookAccount


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory for testing."""
    data_dir = tmp_path / "browser_test_data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def account():
    """Create a Facebook account for testing."""
    return FacebookAccount(
        account_id="test_account",
        email="test@example.com",
        password="test_password",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/100.0.4896.127",
        proxy=None,
        two_factor_secret=None,
        notes="Test account",
        active=True
    )


@pytest.fixture
def browser_manager(tmp_data_dir):
    """Create a browser manager for testing."""
    manager = BrowserManager(data_dir=tmp_data_dir)
    yield manager
    # Cleanup after test
    asyncio.run(manager.close_all())


@pytest.mark.asyncio
async def test_browser_creation(browser_manager):
    """Test browser instance creation."""
    with patch("famp.core.browser.start", new_callable=AsyncMock) as mock_start:
        # Mock browser object
        mock_browser = MagicMock()
        mock_start.return_value = mock_browser
        
        # Get a browser
        browser = await browser_manager.get_browser("test_account", headless=True)
        
        # Verify browser was created correctly
        assert browser == mock_browser
        assert "test_account" in browser_manager.browsers
        mock_start.assert_called_once()
        
        # Arguments should include headless mode
        args = mock_start.call_args[1]["browser_args"]
        assert "--headless=new" in args


@pytest.mark.asyncio
async def test_tab_creation(browser_manager):
    """Test tab creation and cookie loading."""
    with patch("famp.core.browser.start", new_callable=AsyncMock) as mock_start:
        # Mock browser and tab
        mock_tab = AsyncMock()
        mock_browser = MagicMock()
        mock_browser.main_tab = mock_tab
        mock_start.return_value = mock_browser
        
        # Mock load_cookies
        browser_manager.load_cookies = AsyncMock(return_value=True)
        
        # Get a tab
        tab = await browser_manager.get_tab("test_account", headless=True)
        
        # Verify tab was created correctly
        assert tab == mock_tab
        assert "test_account" in browser_manager.active_tabs
        browser_manager.load_cookies.assert_called_once_with("test_account")


@pytest.mark.asyncio
async def test_save_cookies(browser_manager, tmp_data_dir):
    """Test saving cookies."""
    # Mock browser and tab
    mock_tab = AsyncMock()
    mock_cookies = AsyncMock()
    mock_cookies.get_all.return_value = [
        {"name": "test_cookie", "value": "test_value", "domain": "facebook.com"}
    ]
    mock_tab.cookies = mock_cookies
    
    # Add tab to active tabs
    browser_manager.browsers["test_account"] = MagicMock()
    browser_manager.active_tabs["test_account"] = mock_tab
    
    # Save cookies
    result = await browser_manager.save_cookies("test_account")
    
    # Verify cookies were saved correctly
    assert result is True
    cookie_path = tmp_data_dir / "browsers" / "cookies" / "test_account" / "cookies.json"
    assert cookie_path.exists()
    
    # Verify cookie content
    with open(cookie_path, "r") as f:
        cookie_data = json.load(f)
        assert "account_id" in cookie_data
        assert cookie_data["account_id"] == "test_account"
        assert len(cookie_data["cookies"]) == 1
        assert cookie_data["cookies"][0]["name"] == "test_cookie"


@pytest.mark.asyncio
async def test_load_cookies(browser_manager, tmp_data_dir):
    """Test loading cookies."""
    # Create cookie directory and file
    cookie_dir = tmp_data_dir / "browsers" / "cookies" / "test_account"
    cookie_dir.mkdir(parents=True)
    
    # Create test cookie data
    cookie_data = {
        "timestamp": "2024-03-18T12:00:00",
        "account_id": "test_account",
        "expiration": "2025-03-18T12:00:00",
        "cookies": [
            {"name": "test_cookie", "value": "test_value", "domain": "facebook.com"}
        ]
    }
    
    # Write cookie file
    with open(cookie_dir / "cookies.json", "w") as f:
        json.dump(cookie_data, f)
    
    # Mock tab
    mock_tab = AsyncMock()
    mock_cookies = AsyncMock()
    mock_tab.cookies = mock_cookies
    
    # Add tab to active tabs
    browser_manager.active_tabs["test_account"] = mock_tab
    
    # Load cookies
    result = await browser_manager.load_cookies("test_account")
    
    # Verify cookies were loaded correctly
    assert result is True
    mock_cookies.clear.assert_called_once()
    mock_cookies.set.assert_called_once()


@pytest.mark.asyncio
async def test_close_browser(browser_manager):
    """Test closing browser."""
    # Mock browser
    mock_browser = MagicMock()
    browser_manager.browsers["test_account"] = mock_browser
    browser_manager.active_tabs["test_account"] = AsyncMock()
    
    # Mock save_cookies
    browser_manager.save_cookies = AsyncMock(return_value=True)
    
    # Close browser
    result = await browser_manager.close_browser("test_account")
    
    # Verify browser was closed correctly
    assert result is True
    assert "test_account" not in browser_manager.browsers
    assert "test_account" not in browser_manager.active_tabs
    mock_browser.stop.assert_called_once()
    browser_manager.save_cookies.assert_called_once_with("test_account")


@pytest.mark.asyncio
async def test_refresh_cookies(browser_manager):
    """Test refreshing cookies."""
    # Mock tab
    mock_tab = AsyncMock()
    browser_manager.active_tabs["test_account"] = mock_tab
    
    # Mock save_cookies
    browser_manager.save_cookies = AsyncMock(return_value=True)
    
    # Refresh cookies
    result = await browser_manager.refresh_cookies("test_account")
    
    # Verify cookies were refreshed correctly
    assert result is True
    mock_tab.get.assert_called_once_with("https://www.facebook.com")
    browser_manager.save_cookies.assert_called_once_with("test_account")


@pytest.mark.asyncio
async def test_cookie_encryption(browser_manager):
    """Test cookie encryption and decryption."""
    # Set encryption settings
    browser_manager.update_cookie_settings({
        "encryption_enabled": True,
        "encryption_key": "test_encryption_key"
    })
    
    # Test data
    test_data = b'{"test": "data"}'
    
    # Encrypt data
    encrypted = browser_manager._encrypt_data(test_data)
    assert encrypted != test_data
    
    # Decrypt data
    decrypted = browser_manager._decrypt_data(encrypted)
    assert decrypted == test_data


def test_cookie_settings_update(browser_manager):
    """Test updating cookie settings."""
    new_settings = {
        "domain_filter": ["facebook.com"],
        "expiration_days": 60,
        "backup_count": 5
    }
    
    # Update settings
    browser_manager.update_cookie_settings(new_settings)
    
    # Verify settings were updated
    assert browser_manager.cookie_settings["domain_filter"] == ["facebook.com"]
    assert browser_manager.cookie_settings["expiration_days"] == 60
    assert browser_manager.cookie_settings["backup_count"] == 5
    
    # Verify other settings remained unchanged
    assert browser_manager.cookie_settings["encryption_enabled"] is False