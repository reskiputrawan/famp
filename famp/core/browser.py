"""Browser management for FAMP using nodriver."""

import asyncio
import base64
import datetime
import json
import logging
import os
import pickle
import shutil
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union, Any

try:
    from nodriver import Browser, Tab, start
except ImportError:
    raise ImportError(
        "nodriver package is required for FAMP. "
        "Install it with: pip install nodriver"
    )

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages browser instances using nodriver with cookie-based session persistence."""

    def __init__(self, data_dir: Union[str, Path] = None):
        """Initialize browser manager.

        Args:
            data_dir: Directory to store browser data (cookies, etc.)
        """
        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".famp" / "browsers"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.browsers: Dict[str, Browser] = {}
        self.active_tabs: Dict[str, Tab] = {}
        self.cookie_dir = self.data_dir / "cookies"
        self.cookie_dir.mkdir(parents=True, exist_ok=True)

        # Default cookie settings
        self.cookie_settings = {
            "domain_filter": ["facebook.com", "fb.com", "fbcdn.net"],
            "expiration_days": 30,
            "encryption_enabled": False,
            "encryption_key": None,
            "auto_refresh": True,
            "backup_enabled": True,
            "backup_count": 3,
            "use_pickle": True
        }

    async def get_browser(
        self, account_id: str, headless: bool = False, proxy: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Browser:
        """Get or create a browser instance for an account.

        Args:
            account_id: Unique identifier for the account
            headless: Whether to run in headless mode
            proxy: Optional proxy server to use
            user_agent: Optional user agent string

        Returns:
            Browser instance
        """
        if account_id in self.browsers:
            return self.browsers[account_id]

        # Set up browser arguments
        args = []
        if headless:
            args.append("--headless=new")
        if proxy:
            args.append(f"--proxy-server={proxy}")
        if user_agent:
            args.append(f"--user-agent={user_agent}")

        # Add additional arguments for better isolation
        args.extend([
        ])

        # Start browser without user data directory
        browser = await start(browser_args=args)

        self.browsers[account_id] = browser
        logger.info(f"Created new browser instance for account {account_id}")
        return browser

    async def get_tab(self, account_id: str, **browser_kwargs) -> Tab:
        """Get or create a tab for an account.

        Args:
            account_id: Unique identifier for the account
            **browser_kwargs: Additional arguments for get_browser

        Returns:
            Tab object
        """
        browser = await self.get_browser(account_id, **browser_kwargs)

        if account_id in self.active_tabs:
            return self.active_tabs[account_id]

        tab = browser.main_tab
        self.active_tabs[account_id] = tab

        # Load cookies for this account
        await self.load_cookies(account_id)

        return tab

    async def close_browser(self, account_id: str) -> bool:
        """Close browser instance for an account.

        Args:
            account_id: Unique identifier for the account

        Returns:
            True if browser was closed, False otherwise
        """
        # Save cookies before closing
        if account_id in self.active_tabs:
            await self.save_cookies(account_id)
            del self.active_tabs[account_id]

        if account_id in self.browsers:
            browser = self.browsers[account_id]
            browser.stop()
            del self.browsers[account_id]
            logger.info(f"Closed browser instance for account {account_id}")
            return True
        return False

    async def save_cookies(self, account_id: str) -> bool:
        """Save cookies for an account.

        Args:
            account_id: Unique identifier for the account

        Returns:
            True if cookies were saved, False otherwise
        """
        if account_id not in self.browsers:
            logger.warning(f"No active browser session for account {account_id}")
            return False

        browser = self.browsers[account_id]

        try:
            # Create cookie directory for this account if it doesn't exist
            account_cookie_dir = self.cookie_dir / account_id
            account_cookie_dir.mkdir(parents=True, exist_ok=True)

            # Create backup if enabled
            if self.cookie_settings["backup_enabled"]:
                await self._create_cookie_backup(account_id)

            if self.cookie_settings["use_pickle"]:
                # Use direct pickle saving through nodriver
                cookie_path = account_cookie_dir / "cookies.pkl"
                
                if self.cookie_settings["encryption_enabled"] and self.cookie_settings["encryption_key"]:
                    # First save to a temporary file
                    temp_path = account_cookie_dir / "temp_cookies.pkl"
                    await browser.cookies.save(str(temp_path))
                    
                    # Read the pickle file
                    with open(temp_path, "rb") as f:
                        pickle_data = f.read()
                    
                    # Encrypt the pickle data
                    encrypted_data = self._encrypt_data(pickle_data)
                    
                    # Write the encrypted data
                    with open(cookie_path, "wb") as f:
                        f.write(encrypted_data)
                    
                    # Remove the temporary file
                    temp_path.unlink()
                else:
                    # Save directly
                    await browser.cookies.save(str(cookie_path))
                
                logger.info(f"Saved cookies for account {account_id} using pickle format")
            else:
                # Legacy JSON approach
                cookie_path = account_cookie_dir / "cookies.json"
                
                # Get all cookies from the browser - this may not work with nodriver's API
                try:
                    cookies = await browser.cookies.get_all()
                    
                    # Filter cookies by domain if domain filter is enabled
                    if self.cookie_settings["domain_filter"]:
                        filtered_cookies = []
                        for cookie in cookies:
                            domain = cookie.get("domain", "")
                            if any(domain.endswith(d) or domain.startswith(d) for d in self.cookie_settings["domain_filter"]):
                                filtered_cookies.append(cookie)
                        cookies = filtered_cookies
                    
                    # Add metadata to cookies
                    cookie_data = {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "account_id": account_id,
                        "expiration": (datetime.datetime.now() +
                                     datetime.timedelta(days=self.cookie_settings["expiration_days"])).isoformat(),
                        "cookies": cookies
                    }
                    
                    # Encrypt if enabled
                    if self.cookie_settings["encryption_enabled"] and self.cookie_settings["encryption_key"]:
                        encrypted_data = self._encrypt_data(json.dumps(cookie_data).encode())
                        with open(cookie_path, "wb") as f:
                            f.write(encrypted_data)
                    else:
                        with open(cookie_path, "w") as f:
                            json.dump(cookie_data, f, indent=2)
                            
                    logger.info(f"Saved {len(cookies)} cookies for account {account_id} using JSON format")
                except AttributeError:
                    logger.warning("The JSON cookie saving is not compatible with this version of nodriver")
                    return False

            return True
        except Exception as e:
            logger.error(f"Failed to save cookies for account {account_id}: {e}")
            return False

    async def load_cookies(self, account_id: str) -> bool:
        """Load cookies for an account.

        Args:
            account_id: Unique identifier for the account

        Returns:
            True if cookies were loaded, False otherwise
        """
        if account_id not in self.browsers:
            logger.warning(f"No active browser for account {account_id}")
            return False

        browser = self.browsers[account_id]
        account_cookie_dir = self.cookie_dir / account_id
        
        # Check for pickle format first
        pickle_path = account_cookie_dir / "cookies.pkl"
        json_path = account_cookie_dir / "cookies.json"
        
        if self.cookie_settings["use_pickle"] and pickle_path.exists():
            # Use pickle format
            try:
                if self.cookie_settings["encryption_enabled"] and self.cookie_settings["encryption_key"]:
                    # Read the encrypted pickle data
                    with open(pickle_path, "rb") as f:
                        encrypted_data = f.read()
                    
                    # Decrypt the data
                    pickle_data = self._decrypt_data(encrypted_data)
                    
                    # Save to a temporary file
                    temp_path = account_cookie_dir / "temp_cookies.pkl"
                    with open(temp_path, "wb") as f:
                        f.write(pickle_data)
                    
                    # Load the cookies
                    await browser.cookies.load(str(temp_path))
                    
                    # Remove the temporary file
                    temp_path.unlink()
                else:
                    # Load cookies directly
                    await browser.cookies.load(str(pickle_path))
                
                logger.info(f"Loaded cookies for account {account_id} using pickle format")
                return True
            except Exception as e:
                logger.error(f"Failed to load cookies using pickle for account {account_id}: {e}")
                return False
        
        # Fall back to JSON format if pickle not found or not enabled
        elif json_path.exists():
            logger.info(f"Attempting to load legacy JSON cookies for account {account_id}")
            
            try:
                # Load cookie data
                if self.cookie_settings["encryption_enabled"] and self.cookie_settings["encryption_key"]:
                    with open(json_path, "rb") as f:
                        encrypted_data = f.read()
                    cookie_data_str = self._decrypt_data(encrypted_data).decode()
                    cookie_data = json.loads(cookie_data_str)
                else:
                    with open(json_path, "r") as f:
                        cookie_data = json.load(f)

                # Check if cookies are expired
                if "expiration" in cookie_data:
                    expiration = datetime.datetime.fromisoformat(cookie_data["expiration"])
                    if datetime.datetime.now() > expiration:
                        logger.warning(f"Cookies for account {account_id} are expired")
                        if not self.cookie_settings["auto_refresh"]:
                            return False
                        # We'll still load the cookies if auto_refresh is enabled

                # Extract cookies
                cookies = cookie_data.get("cookies", [])

                try:
                    # Clear existing cookies
                    await browser.cookies.clear()
                    
                    # Set cookies
                    for cookie in cookies:
                        try:
                            await browser.cookies.set(cookie)
                        except Exception as e:
                            logger.debug(f"Failed to set cookie: {e}")
                    
                    logger.info(f"Loaded {len(cookies)} cookies for account {account_id} from JSON")
                    
                    # Convert to pickle format for future use if pickle is enabled
                    if self.cookie_settings["use_pickle"]:
                        await self.save_cookies(account_id)
                        logger.info(f"Converted JSON cookies to pickle format for account {account_id}")
                    
                    return True
                except AttributeError:
                    logger.warning("The JSON cookie loading is not compatible with this version of nodriver")
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to load cookies using JSON for account {account_id}: {e}")
                return False
        else:
            logger.warning(f"No saved cookies found for account {account_id}")
            return False

    async def _create_cookie_backup(self, account_id: str) -> bool:
        """Create a backup of cookies for an account.

        Args:
            account_id: Unique identifier for the account

        Returns:
            True if backup was created, False otherwise
        """
        account_cookie_dir = self.cookie_dir / account_id
        
        # Determine file type based on settings
        if self.cookie_settings["use_pickle"]:
            cookie_path = account_cookie_dir / "cookies.pkl"
            extension = "pkl"
        else:
            cookie_path = account_cookie_dir / "cookies.json"
            extension = "json"
        
        if not cookie_path.exists():
            return False

        try:
            # Create backup directory
            backup_dir = account_cookie_dir / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Create backup with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"cookies_{timestamp}.{extension}"

            # Copy cookie file to backup
            shutil.copy2(cookie_path, backup_path)

            # Remove old backups if we have too many
            backups = sorted(backup_dir.glob(f"cookies_*.{extension}"))
            if len(backups) > self.cookie_settings["backup_count"]:
                for old_backup in backups[:-self.cookie_settings["backup_count"]]:
                    old_backup.unlink()

            logger.debug(f"Created cookie backup for account {account_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create cookie backup for account {account_id}: {e}")
            return False

    def _encrypt_data(self, data: bytes) -> bytes:
        """Encrypt data using Fernet symmetric encryption.

        Args:
            data: Data to encrypt

        Returns:
            Encrypted data
        """
        if not self.cookie_settings["encryption_key"]:
            raise ValueError("Encryption key is required for encryption")

        # Convert string key to bytes if needed
        key = self.cookie_settings["encryption_key"]
        if isinstance(key, str):
            key = key.encode()

        # Derive a key from the encryption key
        salt = b'famp_cookie_salt'  # Fixed salt for simplicity
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(key))

        # Create Fernet cipher
        cipher = Fernet(key)

        # Encrypt data
        return cipher.encrypt(data)

    def _decrypt_data(self, encrypted_data: bytes) -> bytes:
        """Decrypt data using Fernet symmetric encryption.

        Args:
            encrypted_data: Encrypted data

        Returns:
            Decrypted data
        """
        if not self.cookie_settings["encryption_key"]:
            raise ValueError("Encryption key is required for decryption")

        # Convert string key to bytes if needed
        key = self.cookie_settings["encryption_key"]
        if isinstance(key, str):
            key = key.encode()

        # Derive a key from the encryption key
        salt = b'famp_cookie_salt'  # Fixed salt for simplicity
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(key))

        # Create Fernet cipher
        cipher = Fernet(key)

        # Decrypt data
        return cipher.decrypt(encrypted_data)

    def update_cookie_settings(self, settings: Dict[str, Any]) -> None:
        """Update cookie settings.

        Args:
            settings: Dictionary of cookie settings to update
        """
        self.cookie_settings.update(settings)
        logger.debug(f"Updated cookie settings: {settings}")

    async def clear_cookies(self, account_id: str) -> bool:
        """Clear cookies for an account.

        Args:
            account_id: Unique identifier for the account

        Returns:
            True if cookies were cleared, False otherwise
        """
        account_cookie_dir = self.cookie_dir / account_id
        json_path = account_cookie_dir / "cookies.json"
        pickle_path = account_cookie_dir / "cookies.pkl"
        
        deleted = False
        
        # Try to delete JSON cookies
        if json_path.exists():
            try:
                json_path.unlink()
                logger.info(f"Cleared JSON cookies for account {account_id}")
                deleted = True
            except Exception as e:
                logger.error(f"Failed to clear JSON cookies for account {account_id}: {e}")
        
        # Try to delete pickle cookies
        if pickle_path.exists():
            try:
                pickle_path.unlink()
                logger.info(f"Cleared pickle cookies for account {account_id}")
                deleted = True
            except Exception as e:
                logger.error(f"Failed to clear pickle cookies for account {account_id}: {e}")
        
        # Clear cookies from browser if it's active
        if account_id in self.browsers:
            try:
                browser = self.browsers[account_id]
                await browser.cookies.clear()
                logger.info(f"Cleared active browser cookies for account {account_id}")
                deleted = True
            except Exception as e:
                logger.error(f"Failed to clear active browser cookies for account {account_id}: {e}")
        
        return deleted

    async def refresh_cookies(self, account_id: str) -> bool:
        """Refresh cookies for an account by visiting Facebook.

        Args:
            account_id: Unique identifier for the account

        Returns:
            True if cookies were refreshed, False otherwise
        """
        if account_id not in self.browsers:
            logger.warning(f"No active browser for account {account_id}")
            return False
        
        browser = self.browsers[account_id]
        
        # Get or create a tab for this browser
        if account_id in self.active_tabs:
            tab = self.active_tabs[account_id]
        else:
            tab = browser.main_tab
            self.active_tabs[account_id] = tab

        try:
            # Visit Facebook to refresh cookies
            await tab.get("https://www.facebook.com")
            await asyncio.sleep(5)  # Wait for cookies to be set

            # Save refreshed cookies
            success = await self.save_cookies(account_id)
            if success:
                logger.info(f"Refreshed cookies for account {account_id}")

            return success
        except Exception as e:
            logger.error(f"Failed to refresh cookies for account {account_id}: {e}")
            return False

    async def close_all(self):
        """Close all browser instances."""
        for account_id in list(self.browsers.keys()):
            await self.close_browser(account_id)
        logger.info("Closed all browser instances")
