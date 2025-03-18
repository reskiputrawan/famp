"""Main implementation for manual login plugin."""

import asyncio
import logging
import time
from typing import Dict, Any, Optional

from nodriver import Tab

from famp.core.account import FacebookAccount
from famp.plugin import Plugin

logger = logging.getLogger(__name__)


class ManualLoginPlugin(Plugin):
    """Plugin for manual Facebook login with guidance and verification."""

    name = "manual_login"
    description = "Guides through manual Facebook login process with verification"
    version = "0.1.0"

    # Facebook URLs
    LOGIN_URL = "https://www.facebook.com/login/"
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

    async def run(self, tab: Tab, account: FacebookAccount) -> Dict[str, Any]:
        """Run the manual login process.

        Args:
            tab: Browser tab to use
            account: Facebook account information

        Returns:
            Dictionary with execution results
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
            # Check if already logged in
            await tab.get(self.HOME_URL)
            await asyncio.sleep(3)  # Wait for page to load
            
            # Check if already logged in
            if await self._is_logged_in(tab):
                logger.info(f"Account {account.account_id} is already logged in")
                if self.config["skip_if_logged_in"]:
                    results.update({
                        "success": True,
                        "logged_in": True,
                        "status": "Already logged in",
                        "message": "Account was already logged in, skipping login process"
                    })
                    return results
            
            # Navigate to login page
            await tab.get(self.LOGIN_URL)
            await asyncio.sleep(2)
            
            # Auto-fill email if configured
            if self.config["auto_fill_email"] and account.email:
                logger.info("Auto-filling email field")
                await tab.execute_script("""
                    document.querySelector('input[name="email"]').value = arguments[0];
                """, account.email)
            
            # Auto-fill password if configured (not recommended for security)
            if self.config["auto_fill_password"] and account.password:
                logger.info("Auto-filling password field")
                await tab.execute_script("""
                    document.querySelector('input[name="pass"]').value = arguments[0];
                """, account.password)
            
            # Inform user about manual login requirement
            print("\n" + "="*50)
            print(f"MANUAL LOGIN REQUIRED for account: {account.email}")
            print("Please complete the login process in the browser window.")
            print("This plugin will wait and verify your login status.")
            if account.two_factor_secret:
                print("NOTE: This account has 2FA enabled. You'll need to enter the code.")
            print("="*50 + "\n")
            
            # Wait for manual login completion
            login_result = await self._wait_for_login_completion(tab)
            
            if login_result["logged_in"]:
                logger.info(f"Manual login successful for account {account.account_id}")
                results.update({
                    "success": True,
                    "logged_in": True,
                    "status": login_result["status"],
                    "message": login_result["message"]
                })
            else:
                logger.warning(f"Manual login failed for account {account.account_id}: {login_result['message']}")
                results.update({
                    "success": False,
                    "logged_in": False,
                    "status": login_result["status"],
                    "message": login_result["message"]
                })
                
        except Exception as e:
            error_msg = f"Error during manual login: {str(e)}"
            logger.error(error_msg)
            results.update({
                "success": False,
                "status": "Error",
                "message": error_msg
            })
        
        # Calculate time taken
        results["time_taken"] = round(time.time() - start_time, 2)
        return results

    async def _is_logged_in(self, tab: Tab) -> bool:
        """Check if user is logged in to Facebook.
        
        Args:
            tab: Browser tab
            
        Returns:
            True if logged in, False otherwise
        """
        # Check for elements that indicate logged-in status
        logged_in_indicators = [
            # Top navigation bar profile link
            "a[href*='/me/']",
            # Facebook logo home link when logged in
            "a[aria-label='Facebook'] svg",
            # User menu button
            "div[aria-label='Your profile'] img",
            # Stories section
            "div[data-pagelet='Stories']",
        ]
        
        for selector in logged_in_indicators:
            try:
                elements = await tab.query_selector_all(selector)
                if elements:
                    return True
            except:
                pass
        
        # Check for login form elements which indicate not logged in
        logout_indicators = [
            "form[action*='/login/']",
            "input[name='email']",
            "input[name='pass']",
            "button[name='login']",
        ]
        
        for selector in logout_indicators:
            try:
                elements = await tab.query_selector_all(selector)
                if elements:
                    return False
            except:
                pass
        
        # If we can't determine for sure, default to not logged in
        return False

    async def _is_checkpoint_page(self, tab: Tab) -> bool:
        """Check if current page is a checkpoint/2FA page.
        
        Args:
            tab: Browser tab
            
        Returns:
            True if on checkpoint page, False otherwise
        """
        # Check URL
        current_url = await tab.get_url()
        if "checkpoint" in current_url:
            return True
        
        # Check for checkpoint elements
        checkpoint_indicators = [
            "input[name='approvals_code']",
            "input#approvals_code",
            "form[action*='/checkpoint/']",
            "button[value='Continue']",
            "div[data-pagelet='Portal/LoginApprovalPage']",
        ]
        
        for selector in checkpoint_indicators:
            try:
                elements = await tab.query_selector_all(selector)
                if elements:
                    return True
            except:
                pass
        
        return False

    async def _wait_for_login_completion(self, tab: Tab) -> Dict[str, Any]:
        """Wait for the manual login process to complete.
        
        Args:
            tab: Browser tab
            
        Returns:
            Dictionary with login status information
        """
        wait_timeout = self.config["wait_timeout"]
        check_interval = self.config["check_interval"]
        
        result = {
            "logged_in": False,
            "status": "Timeout",
            "message": f"Login not completed within {wait_timeout} seconds"
        }
        
        end_time = time.time() + wait_timeout
        
        while time.time() < end_time:
            logger.debug("Checking login status...")
            
            # Check if on checkpoint/2FA page
            if await self._is_checkpoint_page(tab):
                print("2FA/Security checkpoint detected. Please complete verification in the browser.")
                result.update({
                    "status": "Checkpoint",
                    "message": "Waiting for security verification to be completed"
                })
            
            # Check if logged in
            if await self._is_logged_in(tab):
                result.update({
                    "logged_in": True,
                    "status": "Success",
                    "message": "Login completed successfully"
                })
                return result
            
            # Wait before next check
            await asyncio.sleep(check_interval)
            
            # Notify user about remaining time
            remaining = int(end_time - time.time())
            if remaining % 30 == 0:  # Notify every 30 seconds
                print(f"Still waiting for manual login... ({remaining}s remaining)")
        
        return result
    
    async def _detect_login_errors(self, tab: Tab) -> Optional[str]:
        """Detect and return any login error messages.
        
        Args:
            tab: Browser tab
            
        Returns:
            Error message if found, None otherwise
        """
        error_selectors = [
            "div.login_error_box",
            "div._9ay7",
            "div[role='alert']",
            "#error_box",
        ]
        
        for selector in error_selectors:
            try:
                elements = await tab.query_selector_all(selector)
                if elements:
                    error_text = await tab.evaluate(f"document.querySelector('{selector}').textContent")
                    if error_text:
                        return error_text.strip()
            except:
                pass
        
        return None
