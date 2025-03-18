"""Main implementation for manual login plugin."""

import asyncio
import logging
import time
from typing import Dict, Any, Optional

from nodriver import Tab

from famp.core.account import FacebookAccount
from famp.plugin import Plugin, PluginError, ErrorCode
from plugins.login.main import LoginError, TwoFactorError, LoginPlugin

logger = logging.getLogger(__name__)

class ManualLoginError(LoginError):
    """Error raised during manual login process."""
    pass


class ManualLoginPlugin(Plugin):
    """Plugin for manual Facebook login with guidance and verification."""

    name = "manual_login"
    description = "Guides through manual Facebook login process with verification"
    version = "0.1.0"

    # Facebook URLs
    LOGIN_URL = "https://www.facebook.com/"
    HOME_URL = "https://www.facebook.com/"
    CHECKPOINT_URL = "https://www.facebook.com/checkpoint/"

    # Default configuration
    DEFAULT_CONFIG = {
        "wait_timeout": 300,  # Maximum time to wait for manual login (seconds)
        "check_interval": 5,   # How often to check login status (seconds)
        "auto_fill_email": True,  # Whether to auto-fill email address
        "auto_fill_password": False,  # Whether to auto-fill password (default off for security)
        "skip_if_logged_in": True,  # Skip login if already logged in
    }

    def __init__(self):
        """Initialize the plugin."""
        super().__init__()
        self.config.update(self.DEFAULT_CONFIG)
        # Use the improved login detection from LoginPlugin
        self._login_plugin = LoginPlugin()

    async def run(self, tab: Tab, account: FacebookAccount) -> Dict[str, Any]:
        """Run the manual login process.

        Args:
            tab: Browser tab to use
            account: Facebook account information

        Returns:
            Dictionary with execution results

        Raises:
            ManualLoginError: If login process fails
        """
        logger.info(f"Starting manual login process for account {account.account_id}")
        results = {
            "success": False,
            "logged_in": False,
            "time_taken": 0,
            "status": "Not started",
            "message": ""
        }

        start_time = time.time()

        try:
            try:
                # Check if already logged in
                await tab.get(self.HOME_URL)
                await asyncio.sleep(3)  # Wait for page to load

                # Check if already logged in
                if await self._login_plugin.is_logged_in(tab):
                    logger.info(f"Account {account.account_id} is already logged in")
                    if self.config["skip_if_logged_in"]:
                        results.update({
                            "success": True,
                            "logged_in": True,
                            "status": "already_logged_in",
                            "message": "Account was already logged in, skipping login process"
                        })
                        return results

                # Navigate to login page
                await tab.get(self.LOGIN_URL)
                await asyncio.sleep(2)

                # Auto-fill email if configured
                if self.config["auto_fill_email"] and account.email:
                    try:
                        email_field = await tab.select("input[name='email']", timeout=5)
                        if email_field:
                            await email_field.clear_input()
                            await email_field.send_keys(account.email)
                            logger.info("Auto-filled email field")
                    except Exception as e:
                        logger.warning(f"Failed to auto-fill email: {e}")

                # Auto-fill password if configured (not recommended for security)
                if self.config["auto_fill_password"] and account.password:
                    try:
                        password_field = await tab.select("input[name='pass']", timeout=5)
                        if password_field:
                            await password_field.clear_input()
                            await password_field.send_keys(account.password.get_secret_value())
                            logger.info("Auto-filled password field")
                    except Exception as e:
                        logger.warning(f"Failed to auto-fill password: {e}")

                # Inform user about manual login requirement
                print("\n" + "="*50)
                print(f"MANUAL LOGIN REQUIRED for account: {account.email}")
                print("Please complete the login process in the browser window.")
                print("This plugin will wait and verify your login status.")
                if account.two_factor_secret:
                    print("NOTE: This account has 2FA enabled. You'll need to enter the code.")
                print("="*50 + "\n")

                # Wait for manual login completion
                try:
                    is_completed = await self._wait_for_login_completion(tab)
                    if is_completed:
                        logger.info(f"Manual login successful for account {account.account_id}")
                        results.update({
                            "success": True,
                            "logged_in": True,
                            "status": "logged_in",
                            "message": "Manual login completed successfully"
                        })
                    else:
                        raise ManualLoginError(
                            "Manual login timed out",
                            {"timeout": self.config["wait_timeout"]}
                        )

                except TwoFactorError:
                    # Pass through 2FA errors unmodified
                    raise
                except Exception as e:
                    if not isinstance(e, ManualLoginError):
                        e = ManualLoginError(str(e))
                    raise e

            except (TwoFactorError, ManualLoginError) as e:
                logger.error(f"Manual login error: {e}")
                results.update({
                    "success": False,
                    "status": "error",
                    "message": str(e),
                    "error": e.to_dict()
                })
                raise

        finally:
            # Calculate time taken
            results["time_taken"] = round(time.time() - start_time, 2)
            return results

    async def _wait_for_login_completion(self, tab: Tab) -> bool:
        """Wait for the manual login process to complete.

        Args:
            tab: Browser tab

        Returns:
            True if login completed successfully, False otherwise

        Raises:
            TwoFactorError: If 2FA verification is needed
            ManualLoginError: If login fails or times out
        """
        wait_timeout = self.config["wait_timeout"]
        check_interval = self.config["check_interval"]
        end_time = time.time() + wait_timeout

        while time.time() < end_time:
            logger.debug("Checking login status...")

            try:
                # Check if on checkpoint/2FA page
                code_input = await tab.select("#approvals_code", timeout=5)
                if code_input:
                    logger.info("2FA/Security checkpoint detected")
                    raise TwoFactorError(
                        "Manual 2FA verification required",
                        {"remaining_time": int(end_time - time.time())}
                    )

                # Check for login errors
                for selector in [".login_error_box", "div._9ay7", "div[role='alert']"]:
                    error = await tab.select(selector, timeout=2)
                    if error:
                        error_text = await error.text()
                        raise ManualLoginError(
                            f"Login error: {error_text}",
                            {"error_message": error_text}
                        )

                # Use improved login detection from LoginPlugin
                if await self._login_plugin.is_logged_in(tab):
                    return True

            except TwoFactorError:
                raise
            except Exception as e:
                if isinstance(e, ManualLoginError):
                    raise
                logger.debug(f"Login check error: {e}")

            # Notify about remaining time
            remaining = int(end_time - time.time())
            if remaining % 30 == 0:  # Notify every 30 seconds
                logger.info(f"Waiting for manual login... ({remaining}s remaining)")

            await asyncio.sleep(check_interval)

        return False
