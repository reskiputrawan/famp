import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

import nodriver as nd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("famp")

# Directory for storing cookies
COOKIES_DIR = Path("./cookies")
COOKIES_DIR.mkdir(exist_ok=True, parents=True)


class BrowserManager:
    """Manages browser instances using nodriver."""

    def __init__(self, cookies_dir: Path = COOKIES_DIR):
        """Initialize the browser manager.
        
        Args:
            cookies_dir: Directory to store cookies
        """
        self.cookies_dir = cookies_dir
        self.browsers: Dict[str, nd.NoDriver] = {}
        self.cookies_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("famp.browser")

    async def get_browser(self, account_id: str) -> nd.NoDriver:
        """Get or create a browser instance for an account.
        
        Args:
            account_id: Unique identifier for the account
            
        Returns:
            Browser instance for the account
        """
        if account_id in self.browsers and self.browsers[account_id].is_running:
            return self.browsers[account_id]
            
        # Initialize new browser
        browser = nd.NoDriver(
            headless=False,  # For POC, use headed mode for visibility
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        
        # Start the browser
        try:
            await browser.start()
            self.browsers[account_id] = browser
            self.logger.info(f"Started browser for account {account_id}")
            return browser
        except Exception as e:
            self.logger.error(f"Failed to start browser for account {account_id}: {e}")
            raise

    async def close_browser(self, account_id: str) -> None:
        """Close a browser instance.
        
        Args:
            account_id: Unique identifier for the account
        """
        if account_id in self.browsers:
            try:
                await self.browsers[account_id].close()
                del self.browsers[account_id]
                self.logger.info(f"Closed browser for account {account_id}")
            except Exception as e:
                self.logger.error(f"Error closing browser for account {account_id}: {e}")
                
    async def close_all(self) -> None:
        """Close all browser instances."""
        for account_id in list(self.browsers.keys()):
            await self.close_browser(account_id)
            
    async def save_cookies(self, account_id: str, tab: nd.Tab) -> bool:
        """Save cookies for an account.
        
        Args:
            account_id: Unique identifier for the account
            tab: Tab to save cookies from
            
        Returns:
            True if successful, False otherwise
        """
        cookie_path = self.cookies_dir / f"{account_id}.pkl"
        
        try:
            await tab.cookies.save(str(cookie_path))
            self.logger.info(f"Saved cookies for account {account_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save cookies for account {account_id}: {e}")
            return False
            
    async def load_cookies(self, account_id: str, tab: nd.Tab) -> bool:
        """Load cookies for an account into a tab.
        
        Args:
            account_id: Unique identifier for the account
            tab: nodriver Tab object to load cookies into
            
        Returns:
            True if successful, False otherwise
        """
        cookie_path = self.cookies_dir / f"{account_id}.pkl"
        
        if not cookie_path.exists():
            self.logger.warning(f"No cookies found for account {account_id}")
            return False
            
        try:
            await tab.cookies.load(str(cookie_path))
            self.logger.info(f"Loaded cookies for account {account_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load cookies for account {account_id}: {e}")
            return False


class AccountManager:
    """Manages Facebook accounts."""
    
    def __init__(self, accounts_dir: Path = Path("./accounts")):
        """Initialize the account manager.
        
        Args:
            accounts_dir: Directory to store account data
        """
        self.accounts_dir = accounts_dir
        self.accounts_dir.mkdir(parents=True, exist_ok=True)
        self.accounts: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("famp.account")
        self._load_accounts()
        
    def _load_accounts(self) -> None:
        """Load accounts from disk."""
        self.accounts = {}
        
        for account_file in self.accounts_dir.glob("*.txt"):
            account_id = account_file.stem
            
            try:
                with open(account_file, "r") as f:
                    lines = f.read().strip().split("\n")
                    
                if len(lines) >= 2:
                    self.accounts[account_id] = {
                        "username": lines[0],
                        "password": lines[1],
                    }
                    self.logger.info(f"Loaded account {account_id}")
                else:
                    self.logger.error(f"Invalid account file format for {account_id}")
            except Exception as e:
                self.logger.error(f"Failed to load account {account_id}: {e}")
                
    def save_account(self, account_id: str, username: str, password: str) -> bool:
        """Save account credentials.
        
        Args:
            account_id: Unique identifier for the account
            username: Facebook username or email
            password: Facebook password
            
        Returns:
            True if successful, False otherwise
        """
        account_file = self.accounts_dir / f"{account_id}.txt"
        
        try:
            with open(account_file, "w") as f:
                f.write(f"{username}\n{password}")
                
            self.accounts[account_id] = {
                "username": username,
                "password": password,
            }
            
            self.logger.info(f"Saved account {account_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save account {account_id}: {e}")
            return False
            
    def get_account(self, account_id: str) -> Optional[Dict[str, str]]:
        """Get account credentials.
        
        Args:
            account_id: Unique identifier for the account
            
        Returns:
            Account credentials or None if not found
        """
        return self.accounts.get(account_id)
        
    def list_accounts(self) -> List[str]:
        """List all account IDs.
        
        Returns:
            List of account IDs
        """
        return list(self.accounts.keys())
        
    def remove_account(self, account_id: str) -> bool:
        """Remove an account.
        
        Args:
            account_id: Unique identifier for the account
            
        Returns:
            True if successful, False otherwise
        """
        account_file = self.accounts_dir / f"{account_id}.txt"
        
        if not account_file.exists():
            self.logger.warning(f"Account {account_id} does not exist")
            return False
            
        try:
            account_file.unlink()
            
            if account_id in self.accounts:
                del self.accounts[account_id]
                
            self.logger.info(f"Removed account {account_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove account {account_id}: {e}")
            return False


class PluginManager:
    """Manages plugins for Facebook automation."""

    def __init__(self):
        """Initialize the plugin manager."""
        self.plugins = {}
        self.logger = logging.getLogger("famp.plugin")

    def register_plugin(self, name: str, plugin: Any) -> None:
        """Register a plugin.

        Args:
            name: Name of the plugin
            plugin: Plugin instance
        """
        self.plugins[name] = plugin
        self.logger.info(f"Registered plugin: {name}")

    def get_plugin(self, name: str) -> Optional[Any]:
        """Get a plugin by name.

        Args:
            name: Name of the plugin

        Returns:
            Plugin instance or None if not found
        """
        return self.plugins.get(name)

    def list_plugins(self) -> List[str]:
        """List all plugin names.

        Returns:
            List of plugin names
        """
        return list(self.plugins.keys())


class LoginPlugin:
    """Plugin for Facebook login automation."""

    def __init__(self):
        """Initialize the plugin."""
        self.logger = logging.getLogger("famp.plugin.login")

    async def run(self, tab: nd.Tab, account: Dict[str, str]) -> Dict[str, Any]:
        """Run the login automation.

        Args:
            tab: nodriver Tab object
            account: Account credentials

        Returns:
            Result of the automation
        """
        try:
            # Navigate to Facebook
            await tab.get("https://www.facebook.com/")
            self.logger.info("Navigated to Facebook")

            # Check if already logged in
            try:
                # Look for an element that indicates we're logged in
                await tab.wait_for_selector('[aria-label="Facebook"]', timeout=5000)
                self.logger.info("Already logged in")
                return {"status": "success", "message": "Already logged in"}
            except:
                self.logger.info("Not logged in, proceeding with login")

            # Fill in email/username
            email_input = await tab.wait_for_selector('input[name="email"]')
            await email_input.type(account["username"])
            self.logger.info("Entered username")

            # Fill in password
            password_input = await tab.wait_for_selector('input[name="pass"]')
            await password_input.type(account["password"])
            self.logger.info("Entered password")

            # Click login button
            login_button = await tab.wait_for_selector('button[name="login"]')
            await login_button.click()
            self.logger.info("Clicked login button")

            # Wait for navigation to complete
            await tab.wait_for_navigation()

            # Check for successful login
            try:
                # Look for an element that indicates we're logged in
                await tab.wait_for_selector('[aria-label="Facebook"]', timeout=10000)
                self.logger.info("Login successful")
                return {"status": "success", "message": "Login successful"}
            except:
                self.logger.error("Login failed")
                return {"status": "error", "message": "Login failed"}

        except Exception as e:
            self.logger.error(f"Login error: {e}")
            return {"status": "error", "message": str(e)}


async def main():
    """Run the FAMP POC."""
    logger.info("Starting FAMP POC")
    
    # Initialize managers
    browser_manager = BrowserManager()
    account_manager = AccountManager()
    plugin_manager = PluginManager()
    
    # Register plugins
    login_plugin = LoginPlugin()
    plugin_manager.register_plugin("login", login_plugin)
    
    try:
        # Check for accounts
        accounts = account_manager.list_accounts()
        
        if not accounts:
            # Create a sample account if none exist
            print("No accounts found. Please enter Facebook credentials:")
            account_id = input("Account ID (e.g., work, personal): ")
            username = input("Email or Phone: ")
            password = input("Password: ")
            
            account_manager.save_account(account_id, username, password)
            accounts = [account_id]
            
        # Run login plugin for first account
        account_id = accounts[0]
        account = account_manager.get_account(account_id)
        
        if account:
            # Get browser for account
            browser = await browser_manager.get_browser(account_id)
            tab = await browser.new_tab()
            
            # Try to load cookies
            await browser_manager.load_cookies(account_id, tab)
            
            # Run login plugin
            login_plugin = plugin_manager.get_plugin("login")
            result = await login_plugin.run(tab, account)
            
            print(f"Login result: {result}")
            
            # Save cookies if login successful
            if result["status"] == "success":
                await browser_manager.save_cookies(account_id, tab)
                
            # Keep browser open for demonstration
            print("Press Enter to close the browser...")
            input()
        
    finally:
        # Clean up
        await browser_manager.close_all()
        logger.info("FAMP POC completed")


if __name__ == "__main__":
    asyncio.run(main())
