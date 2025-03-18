"""Facebook login plugin implementation."""

import asyncio
import base64
import logging
import re
from enum import Enum
from typing import Dict, Any, Optional, List

import pyotp
from nodriver import Tab

from famp.core.account import FacebookAccount
from famp.plugin import Plugin, PluginError, ErrorCode

logger = logging.getLogger(__name__)

class TwoFactorMethod(str, Enum):
    """Two-factor authentication methods."""
    TOTP = "totp"
    SMS = "sms"
    EMAIL = "email"
    BACKUP_CODE = "backup_code"
    UNKNOWN = "unknown"

class LoginError(PluginError):
    """Error raised during login process."""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.AUTHENTICATION_ERROR, message, "login", context)

class TwoFactorError(LoginError):
    """Error raised during two-factor authentication."""
    pass

class LoginPlugin(Plugin):
    """Plugin for automating Facebook login."""

    name = "login"
    description = "Automates Facebook login process with enhanced 2FA support"
    version = "0.2.0"

    _2FA_SELECTORS = {
        "code_input": "#approvals_code",
        "submit_button": "button[type='submit']",
        "sms_option": "a[href*='sms']",
        "email_option": "a[href*='email']",
        "backup_code_option": "a[href*='recovery']",
        "remember_browser": "input[name='name_action_selected']"
    }

    def __init__(self):
        """Initialize login plugin."""
        super().__init__()
        self.config = {
            "max_attempts": 3,
            "attempt_delay": 5,
            "login_url": "https://www.facebook.com/login",
            "timeout": 30,
            "check_logged_in": True,
            "remember_browser": True,
            "preferred_2fa_method": TwoFactorMethod.TOTP
        }

    async def detect_2fa_type(self, tab: Tab) -> TwoFactorMethod:
        """Detect the type of 2FA challenge presented.

        Args:
            tab: nodriver Tab object

        Returns:
            TwoFactorMethod indicating the type of 2FA detected
        """
        # Check for code input field
        code_input = await tab.select(self._2FA_SELECTORS["code_input"], timeout=5)
        if not code_input:
            return TwoFactorMethod.UNKNOWN

        # Look for method indicators in the page content
        page_text = await tab.text()

        if any(indicator in page_text.lower() for indicator in ["authenticator", "authentication app"]):
            return TwoFactorMethod.TOTP
        elif "text message" in page_text.lower() or "sms" in page_text.lower():
            return TwoFactorMethod.SMS
        elif "email" in page_text.lower():
            return TwoFactorMethod.EMAIL
        elif any(indicator in page_text.lower() for indicator in ["recovery", "backup", "login code"]):
            return TwoFactorMethod.BACKUP_CODE

        return TwoFactorMethod.UNKNOWN

    def generate_totp_code(self, secret: str) -> str:
        """Generate TOTP code from secret.

        Args:
            secret: TOTP secret key

        Returns:
            Generated TOTP code

        Raises:
            TwoFactorError: If secret is invalid
        """
        try:
            # Clean up secret (remove spaces, normalize)
            secret = secret.replace(" ", "").upper()

            # Handle base32 padding
            padding = len(secret) % 8
            if padding:
                secret += "=" * (8 - padding)

            # Validate secret
            try:
                base64.b32decode(secret, casefold=True)
            except Exception:
                raise TwoFactorError(
                    "Invalid TOTP secret",
                    {"secret_length": len(secret)}
                )

            # Generate code
            totp = pyotp.TOTP(secret)
            return totp.now()

        except Exception as e:
            raise TwoFactorError(
                f"Failed to generate TOTP code: {str(e)}",
                {"error": str(e)}
            )

    async def handle_2fa(
        self,
        tab: Tab,
        account: FacebookAccount,
        method: Optional[TwoFactorMethod] = None
    ) -> bool:
        """Handle two-factor authentication challenge.

        Args:
            tab: nodriver Tab object
            account: Facebook account
            method: Optional preferred 2FA method

        Returns:
            True if 2FA completed successfully, False otherwise

        Raises:
            TwoFactorError: If 2FA fails
        """
        # Detect 2FA type if not specified
        detected_method = await self.detect_2fa_type(tab)
        if detected_method == TwoFactorMethod.UNKNOWN:
            raise TwoFactorError("Could not detect 2FA method")

        # Use preferred method if possible
        method = method or self.config["preferred_2fa_method"]

        try:
            if method == TwoFactorMethod.TOTP and account.two_factor_secret:
                # Generate and enter TOTP code
                code = self.generate_totp_code(account.two_factor_secret.get_secret_value())
                success = await self._submit_2fa_code(tab, code)
                if success:
                    return True

                # TOTP failed, try SMS as fallback
                method = TwoFactorMethod.SMS

            if method == TwoFactorMethod.SMS:
                # Click SMS option if available
                sms_button = await tab.select(self._2FA_SELECTORS["sms_option"])
                if sms_button:
                    await sms_button.click()
                    await asyncio.sleep(2)

                # Wait for user to enter code
                logger.info("Waiting for SMS code to be entered manually...")
                await self._wait_for_manual_code(tab)
                return True

            elif method == TwoFactorMethod.EMAIL:
                # Click email option if available
                email_button = await tab.select(self._2FA_SELECTORS["email_option"])
                if email_button:
                    await email_button.click()
                    await asyncio.sleep(2)

                # Wait for user to enter code
                logger.info("Waiting for email code to be entered manually...")
                await self._wait_for_manual_code(tab)
                return True

            elif method == TwoFactorMethod.BACKUP_CODE:
                # Click backup code option if available
                backup_button = await tab.select(self._2FA_SELECTORS["backup_code_option"])
                if backup_button:
                    await backup_button.click()
                    await asyncio.sleep(2)

                # Wait for user to enter backup code
                logger.info("Waiting for backup code to be entered manually...")
                await self._wait_for_manual_code(tab)
                return True

            raise TwoFactorError(
                f"Unsupported 2FA method: {method}",
                {"method": method}
            )

        except Exception as e:
            if not isinstance(e, TwoFactorError):
                e = TwoFactorError(str(e))
            raise e

    async def _submit_2fa_code(self, tab: Tab, code: str) -> bool:
        """Submit 2FA code and handle response.

        Args:
            tab: nodriver Tab object
            code: 2FA code to submit

        Returns:
            True if code accepted, False otherwise
        """
        try:
            # Find and fill code input
            code_input = await tab.select(self._2FA_SELECTORS["code_input"])
            if not code_input:
                return False

            await code_input.clear_input()
            await code_input.send_keys(code)

            # Check "remember browser" if configured
            if self.config["remember_browser"]:
                remember = await tab.select(self._2FA_SELECTORS["remember_browser"])
                if remember:
                    await remember.click()

            # Submit code
            submit = await tab.select(self._2FA_SELECTORS["submit_button"])
            if not submit:
                return False

            await submit.click()
            await asyncio.sleep(5)

            # Check for errors
            error = await tab.select(".uiHeaderTitle")
            if error:
                error_text = await error.text()
                if "incorrect" in error_text.lower():
                    return False

            # Check if we're past 2FA
            code_input = await tab.select(self._2FA_SELECTORS["code_input"])
            return not code_input

        except Exception as e:
            logger.error(f"Error submitting 2FA code: {e}")
            return False

    async def _wait_for_manual_code(self, tab: Tab, timeout: int = 300) -> None:
        """Wait for user to manually enter 2FA code.

        Args:
            tab: nodriver Tab object
            timeout: Maximum time to wait in seconds

        Raises:
            TwoFactorError: If timeout reached or verification fails
        """
        end_time = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < end_time:
            # Check if we're past 2FA
            code_input = await tab.select(self._2FA_SELECTORS["code_input"])
            if not code_input:
                return

            # Check for errors
            error = await tab.select(".uiHeaderTitle")
            if error:
                error_text = await error.text()
                if "incorrect" in error_text.lower():
                    raise TwoFactorError("Incorrect 2FA code entered")

            await asyncio.sleep(2)

        raise TwoFactorError(f"2FA verification timed out after {timeout}s")

    async def is_logged_in(self, tab: Tab) -> bool:
        """Check if user is already logged in.

        Args:
            tab: nodriver Tab object

        Returns:
            True if user is logged in, False otherwise
        """
        try:
            logged_in_indicators = [
                # Profile menu
                "div[aria-label*='Your profile']",
                "div[aria-label*='Profil Anda']",
                # News Feed
                "div[aria-label='News Feed']",
                "div[role='main']",
                # Create post box
                "div[aria-label*='Create']",
                # Messenger
                "div[aria-label='Messenger']"
            ]

            for selector in logged_in_indicators:
                element = await tab.select(selector, timeout=5)
                if element:
                    return True

            # Check URL for login-related paths
            # current_url = await tab.get_url()
            # if not any(path in current_url for path in ["/login", "/checkpoint"]):
            #     # Additional check for profile-related elements
            #     profile_elements = await tab.find("your profile", best_match=True, timeout=5)
            #     if profile_elements:
            #         return True

            return False

        except Exception:
            return False

    async def run(self, tab: Tab, account: FacebookAccount) -> Dict[str, Any]:
        """Run the login process.

        Args:
            tab: nodriver Tab object
            account: Facebook account to use

        Returns:
            Dictionary with login results

        Raises:
            LoginError: If login fails
        """
        results = {
            "success": False,
            "logged_in": False,
            "two_factor_required": False,
            "two_factor_method": None
        }

        # Check if already logged in
        if self.config["check_logged_in"]:
            await tab.get("https://www.facebook.com")
            if await self.is_logged_in(tab):
                logger.info(f"Account {account.account_id} is already logged in")
                results.update({
                    "success": True,
                    "logged_in": True,
                    "status": "already_logged_in"
                })
                return results

        # Navigate to login page
        await tab.get(self.config["login_url"])

        # Multiple attempts
        for attempt in range(1, self.config["max_attempts"] + 1):
            try:
                logger.info(f"Login attempt {attempt} for account {account.account_id}")

                # Find email and password fields
                email_field = await tab.select("input[name='email']", timeout=10)
                if not email_field:
                    if attempt < self.config["max_attempts"]:
                        await asyncio.sleep(self.config["attempt_delay"])
                        continue
                    raise LoginError("Email field not found")

                password_field = await tab.select("input[name='pass']", timeout=5)
                if not password_field:
                    if attempt < self.config["max_attempts"]:
                        await asyncio.sleep(self.config["attempt_delay"])
                        continue
                    raise LoginError("Password field not found")

                # Fill in credentials
                await email_field.clear_input()
                await email_field.send_keys(account.email)

                await password_field.clear_input()
                await password_field.send_keys(account.password.get_secret_value())

                # Find and click login button
                login_button = await tab.select("button[name='login']", timeout=5)
                if not login_button:
                    if attempt < self.config["max_attempts"]:
                        await asyncio.sleep(self.config["attempt_delay"])
                        continue
                    raise LoginError("Login button not found")

                await login_button.click()
                await asyncio.sleep(5)

                # Check for errors
                error_selectors = [
                    ".uiHeaderTitle",
                    "#error_box",
                    "div[role='alert']"
                ]

                for selector in error_selectors:
                    error = await tab.select(selector, timeout=5)
                    if error:
                        error_text = await error.text()
                        if any(msg in error_text.lower() for msg in ["incorrect", "invalid", "wrong"]):
                            raise LoginError(
                                "Invalid credentials",
                                {"error_message": error_text}
                            )
                        logger.warning(f"Login error: {error_text}")
                        if attempt < self.config["max_attempts"]:
                            await asyncio.sleep(self.config["attempt_delay"])
                            continue

                # Check for 2FA
                if await tab.select(self._2FA_SELECTORS["code_input"], timeout=5):
                    logger.info("Two-factor authentication required")

                    # Detect 2FA method
                    method = await self.detect_2fa_type(tab)
                    results["two_factor_required"] = True
                    results["two_factor_method"] = method

                    if account.two_factor_secret or method in [TwoFactorMethod.SMS, TwoFactorMethod.EMAIL]:
                        try:
                            await self.handle_2fa(tab, account, method)
                            # Wait to ensure we're fully logged in
                            await asyncio.sleep(5)
                        except TwoFactorError as e:
                            raise LoginError(
                                str(e),
                                {"two_factor_method": method}
                            )
                    else:
                        raise LoginError(
                            "Two-factor authentication required but no method available",
                            {"two_factor_method": method}
                        )

                # Final check if login was successful
                if await self.is_logged_in(tab):
                    logger.info(f"Successfully logged in account {account.account_id}")
                    results.update({
                        "success": True,
                        "logged_in": True,
                        "status": "logged_in"
                    })
                    return results

            except LoginError:
                raise
            except Exception as e:
                logger.error(f"Login error: {e}")
                if attempt < self.config["max_attempts"]:
                    await asyncio.sleep(self.config["attempt_delay"])
                    continue
                raise LoginError(str(e))

        # If all attempts failed
        raise LoginError(
            "Login failed after maximum attempts",
            {
                "attempts": self.config["max_attempts"],
                "last_url": await tab.get_url()
            }
        )
