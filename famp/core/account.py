"""Account management for FAMP."""

import base64
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, SecretStr

logger = logging.getLogger(__name__)


class FacebookAccount(BaseModel):
    """Model for storing Facebook account data."""

    account_id: str
    email: str
    password: SecretStr
    user_agent: Optional[str] = None
    proxy: Optional[str] = None
    two_factor_secret: Optional[SecretStr] = None
    notes: Optional[str] = None
    active: bool = True


class AccountManager:
    """Manages Facebook accounts and credentials."""

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize account manager.

        Args:
            data_dir: Directory to store account data
        """
        self.data_dir = data_dir or Path.home() / ".famp" / "accounts"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.accounts_file = self.data_dir / "accounts.json"
        self.accounts: Dict[str, FacebookAccount] = {}
        self._load_accounts()

    def _load_accounts(self):
        """Load accounts from storage."""
        if not self.accounts_file.exists():
            logger.info("No accounts file found, creating new one")
            self._save_accounts()
            return

        try:
            with open(self.accounts_file, "r") as f:
                accounts_data = json.load(f)

            for account_data in accounts_data:
                # Convert plain password to SecretStr
                if isinstance(account_data.get("password"), str):
                    password = account_data["password"]
                    decrypted = self._decrypt_password(password)
                    account_data["password"] = SecretStr(decrypted)

                # Convert plain two_factor_secret to SecretStr if exists
                if isinstance(account_data.get("two_factor_secret"), str):
                    two_factor = account_data["two_factor_secret"]
                    decrypted = self._decrypt_password(two_factor)
                    account_data["two_factor_secret"] = SecretStr(decrypted)

                account = FacebookAccount(**account_data)
                self.accounts[account.account_id] = account

            logger.info(f"Loaded {len(self.accounts)} accounts")
        except Exception as e:
            logger.error(f"Error loading accounts: {e}")
            # Create new accounts file if loading fails
            self._save_accounts()

    def _save_accounts(self):
        """Save accounts to storage."""
        try:
            accounts_data = []
            for account in self.accounts.values():
                account_dict = account.model_dump()

                # Convert SecretStr to encrypted string
                if isinstance(account.password, SecretStr):
                    account_dict["password"] = self._encrypt_password(account.password.get_secret_value())
                
                # Convert two_factor_secret if exists
                if account.two_factor_secret and isinstance(account.two_factor_secret, SecretStr):
                    account_dict["two_factor_secret"] = self._encrypt_password(
                        account.two_factor_secret.get_secret_value()
                    )

                accounts_data.append(account_dict)

            with open(self.accounts_file, "w") as f:
                json.dump(accounts_data, f, indent=2)

            logger.info(f"Saved {len(self.accounts)} accounts")
        except Exception as e:
            logger.error(f"Error saving accounts: {e}")

    def _encrypt_password(self, password: str) -> str:
        """Simple encryption for passwords (for demo purposes).

        In production, use a proper encryption library.

        Args:
            password: Plain text password

        Returns:
            Encrypted password string
        """
        return base64.b64encode(password.encode()).decode()

    def _decrypt_password(self, encrypted: str) -> str:
        """Simple decryption for passwords (for demo purposes).

        Args:
            encrypted: Encrypted password string

        Returns:
            Original password as a string
        """
        try:
            decrypted = base64.b64decode(encrypted.encode()).decode()
            return decrypted
        except Exception as e:
            logger.error(f"Error decrypting password: {e}")
            return ""

    def add_account(self, account: FacebookAccount) -> bool:
        """Add a new Facebook account.

        Args:
            account: FacebookAccount object

        Returns:
            True if account was added, False otherwise
        """
        if account.account_id in self.accounts:
            logger.warning(f"Account {account.account_id} already exists")
            return False

        self.accounts[account.account_id] = account
        self._save_accounts()
        logger.info(f"Added account {account.account_id}")
        return True

    def get_account(self, account_id: str) -> Optional[FacebookAccount]:
        """Get account by ID.

        Args:
            account_id: Unique account identifier

        Returns:
            FacebookAccount object or None if not found
        """
        return self.accounts.get(account_id)

    def update_account(self, account: FacebookAccount) -> bool:
        """Update an existing account.

        Args:
            account: FacebookAccount object with updates

        Returns:
            True if account was updated, False otherwise
        """
        if account.account_id not in self.accounts:
            logger.warning(f"Account {account.account_id} does not exist")
            return False

        self.accounts[account.account_id] = account
        self._save_accounts()
        logger.info(f"Updated account {account.account_id}")
        return True

    def delete_account(self, account_id: str) -> bool:
        """Delete an account.

        Args:
            account_id: Unique account identifier

        Returns:
            True if account was deleted, False otherwise
        """
        if account_id not in self.accounts:
            logger.warning(f"Account {account_id} does not exist")
            return False

        del self.accounts[account_id]
        self._save_accounts()
        logger.info(f"Deleted account {account_id}")
        return True

    def list_accounts(self) -> List[FacebookAccount]:
        """List all accounts.

        Returns:
            List of FacebookAccount objects
        """
        return list(self.accounts.values())
