"""Tests for enhanced login plugin functionality."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from famp.core.account import FacebookAccount
from plugins.login.main import (
    LoginPlugin,
    LoginError,
    TwoFactorError,
    TwoFactorMethod
)

@pytest.fixture
def account():
    """Create a test account."""
    return FacebookAccount(
        account_id="test_account",
        email="test@example.com",
        password="test_password",
        user_agent="Test User Agent",
        proxy=None,
        two_factor_secret="JBSWY3DPEHPK3PXP",  # Test TOTP secret
        notes="Test account",
        active=True
    )

@pytest.fixture
def plugin():
    """Create a login plugin instance."""
    return LoginPlugin()

@pytest.fixture
def mock_tab():
    """Create a mock browser tab."""
    tab = AsyncMock()

    # Mock base methods
    tab.get = AsyncMock()
    tab.text = AsyncMock(return_value="")
    tab.get_url = AsyncMock(return_value="https://www.facebook.com")

    # Mock Element class for selectors
    class Element:
        def __init__(self):
            self.click = AsyncMock()
            self.clear_input = AsyncMock()
            self.send_keys = AsyncMock()
            self.text = AsyncMock(return_value="")

    # Mock selector methods to return Element instances
    async def select(selector, timeout=None):
        return Element()
    tab.select = AsyncMock(side_effect=select)

    return tab

@pytest.mark.asyncio
async def test_totp_generation(plugin, account):
    """Test TOTP code generation."""
    # Test valid secret
    code = plugin.generate_totp_code(account.two_factor_secret.get_secret_value())
    assert len(code) == 6
    assert code.isdigit()

    # Test invalid secret
    with pytest.raises(TwoFactorError):
        plugin.generate_totp_code("invalid-secret")

@pytest.mark.asyncio
async def test_2fa_detection(plugin, mock_tab):
    """Test 2FA method detection."""
    # Test TOTP detection
    mock_tab.text = AsyncMock(return_value="authentication app code")
    method = await plugin.detect_2fa_type(mock_tab)
    assert method == TwoFactorMethod.TOTP

    # Test SMS detection
    mock_tab.text = AsyncMock(return_value="text message verification")
    method = await plugin.detect_2fa_type(mock_tab)
    assert method == TwoFactorMethod.SMS

    # Test email detection
    mock_tab.text = AsyncMock(return_value="email verification code")
    method = await plugin.detect_2fa_type(mock_tab)
    assert method == TwoFactorMethod.EMAIL

    # Test backup code detection
    mock_tab.text = AsyncMock(return_value="recovery code")
    method = await plugin.detect_2fa_type(mock_tab)
    assert method == TwoFactorMethod.BACKUP_CODE

@pytest.mark.asyncio
async def test_2fa_handling(plugin, mock_tab, account):
    """Test 2FA handling."""
    # Mock successful TOTP verification
    mock_tab.select = AsyncMock(side_effect=[
        AsyncMock(),  # code input field
        AsyncMock(),  # submit button
        None,  # No code input field after submit (success)
    ])

    success = await plugin.handle_2fa(mock_tab, account, TwoFactorMethod.TOTP)
    assert success is True

    # Test SMS fallback
    mock_tab.select = AsyncMock(side_effect=[
        AsyncMock(),  # code input field
        AsyncMock(text=AsyncMock(return_value="incorrect")),  # error message
        AsyncMock(),  # sms option
        None,  # success
    ])

    success = await plugin.handle_2fa(mock_tab, account)
    assert success is True

@pytest.mark.asyncio
async def test_login_error_handling(plugin, mock_tab, account):
    """Test login error handling."""
    # Test invalid credentials
    mock_tab.select = AsyncMock(side_effect=[
        AsyncMock(),  # email field
        AsyncMock(),  # password field
        AsyncMock(),  # login button
        AsyncMock(text=AsyncMock(return_value="incorrect password"))  # error message
    ])

    with pytest.raises(LoginError) as exc:
        await plugin.run(mock_tab, account)
    assert "Invalid credentials" in str(exc.value)

    # Test missing 2FA method
    account.two_factor_secret = None
    mock_tab.select = AsyncMock(side_effect=[
        AsyncMock(),  # email field
        AsyncMock(),  # password field
        AsyncMock(),  # login button
        AsyncMock(),  # 2FA input field
    ])

    with pytest.raises(LoginError) as exc:
        await plugin.run(mock_tab, account)
    assert "Two-factor authentication required" in str(exc.value)

@pytest.mark.asyncio
async def test_retry_behavior(plugin, mock_tab, account):
    """Test retry behavior for transient errors."""
    # Setup mock to fail twice then succeed
    side_effects = [
        AsyncMock(),  # email field
        AsyncMock(),  # password field
        AsyncMock(),  # login button
        Exception("Network error"),  # First attempt fails
        AsyncMock(),  # email field (retry 1)
        AsyncMock(),  # password field
        AsyncMock(),  # login button
        Exception("Network error"),  # Second attempt fails
        AsyncMock(),  # email field (retry 2)
        AsyncMock(),  # password field
        AsyncMock(),  # login button
        AsyncMock(),  # Success indicators
    ]
    mock_tab.select = AsyncMock(side_effect=side_effects)

    # Configure retry settings
    plugin.config.update({
        "max_attempts": 3,
        "attempt_delay": 0.1
    })

    results = await plugin.run(mock_tab, account)
    assert results["success"] is True
    assert results["logged_in"] is True

@pytest.mark.asyncio
async def test_login_detection(plugin, mock_tab):
    """Test login state detection."""
    # Test logged in detection
    mock_tab.select = AsyncMock(side_effect=[
        AsyncMock(),  # profile menu
        AsyncMock(),  # news feed
    ])
    assert await plugin.is_logged_in(mock_tab) is True

    # Test logged out detection
    mock_tab.select = AsyncMock(return_value=None)
    mock_tab.get_url = AsyncMock(return_value="https://www.facebook.com/login")
    assert await plugin.is_logged_in(mock_tab) is False
