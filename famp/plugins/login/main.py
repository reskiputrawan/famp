"""Facebook login plugin implementation."""

import asyncio
import logging
import time
from typing import Dict, Any, Optional

from nodriver import Tab

from famp.core.account import FacebookAccount
from famp.plugin import Plugin

logger = logging.getLogger(__name__)


class LoginPlugin(Plugin):
    """Plugin for automating Facebook login."""

    name = "login"
    description = "Automates Facebook login process"
    version = "0.1.0"

    def __init__(self):
        """Initialize login plugin."""
        super().__init__()
        self.config = {
            "max_attempts": 3,
            "attempt_delay": 5,
            "login_url": "https://www.facebook.com/login",
            "timeout": 30,
            "check_logged_in": True
        }

    async def is_logged_in(self, tab: Tab) -> bool:
        """Check if user is already logged in.

        Args:
            tab: nodriver Tab object

        Returns:
            True if user is logged in, False otherwise
        """
        try:
            # Try to find elements that indicate user is logged in
            profile_link = await tab.find("your profile", best_match=True, timeout=5)
            if profile_link:
                return True

            # Check for feed elements
            feed = await tab.select("[aria-label='News Feed']", timeout=5)
            if feed:
                return True

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
        """
        # Check if already logged in
        if self.config["check_logged_in"]:
            await tab.get("https://www.facebook.com")
            if await self.is_logged_in(tab):
                logger.info(f"Account {account.account_id} is already logged in")
                return {"success": True, "status": "already_logged_in"}

        # Navigate to login page
        await tab.get(self.config["login_url"])

        # Multiple attempts
        for attempt in range(1, self.config["max_attempts"] + 1):
            try:
                logger.info(f"Login attempt {attempt} for account {account.account_id}")

                # Find email and password fields
                email_field = await tab.select("input[name='email']", timeout=10)
                if not email_field:
                    logger.warning("Email field not found")
                    continue

                password_field = await tab.select("input[name='pass']", timeout=5)
                if not password_field:
                    logger.warning("Password field not found")
                    continue

                # Fill in credentials
                await email_field.clear_input()
                await email_field.send_keys(account.email)

                await password_field.clear_input()
                await password_field.send_keys(account.password.get_secret_value())

                # Find and click login button
                login_button = await tab.select("button[name='login']", timeout=5)
                if not login_button:
                    logger.warning("Login button not found")
                    continue

                await login_button.click()

                # Wait for login to complete
                await asyncio.sleep(5)

                # Check for errors or success
                error_message = await tab.select(".uiHeaderTitle", timeout=5)
                if error_message:
                    error_text = await error_message.text()
                    logger.warning(f"Login error: {error_text}")

                    if attempt < self.config["max_attempts"]:
                        await asyncio.sleep(self.config["attempt_delay"])
                    continue

                # Check for 2FA
                two_factor = await tab.select("#approvals_code", timeout=5)
                if two_factor:
                    logger.info("Two-factor authentication required")
                    if account.two_factor_secret:
                        # Implement 2FA code generation here
                        two_factor_code = "123456"  # Placeholder, should generate from account.two_factor_secret
                        await two_factor.send_keys(two_factor_code)

                        submit_btn = await tab.find("submit", best_match=True)
                        if submit_btn:
                            await submit_btn.click()
                            await asyncio.sleep(5)
                    else:
                        return {
                            "success": False,
                            "status": "two_factor_required",
                            "message": "Two-factor authentication required but no secret provided"
                        }

                # Check if login was successful
                if await self.is_logged_in(tab):
                    logger.info(f"Successfully logged in account {account.account_id}")
                    return {"success": True, "status": "logged_in"}
            except Exception as e:
                logger.error(f"Login error: {e}")
                if attempt < self.config["max_attempts"]:
                    await asyncio.sleep(self.config["attempt_delay"])

        # If all attempts failed
        return {"success": False, "status": "login_failed", "attempts": self.config["max_attempts"]}
