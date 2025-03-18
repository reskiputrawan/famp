#!/usr/bin/env python3
"""Test script for manual login plugin."""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path to import FAMP modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from famp.core.account import FacebookAccount
from famp.core.browser import BrowserManager
from famp.plugins.manual_login.main import ManualLoginPlugin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Example configuration
test_config = {
    "wait_timeout": 300,
    "check_interval": 5,
    "auto_fill_email": True,
    "auto_fill_password": False,
    "skip_if_logged_in": True
}

async def test_manual_login():
    """Test the manual login plugin."""
    # Create a test account
    account = FacebookAccount(
        account_id="test_account",
        email="your_email@example.com",  # Replace with test email
        password="your_password",        # Replace with test password
        user_agent=None,
        proxy=None,
        two_factor_secret=None,
        notes="Test account for manual login",
        active=True
    )
    
    # Initialize browser manager
    browser_manager = BrowserManager()
    
    try:
        # Get a browser tab (non-headless for manual interaction)
        tab = await browser_manager.get_tab(account.account_id, headless=False)
        
        # Initialize the plugin
        plugin = ManualLoginPlugin()
        plugin.configure(test_config)
        
        # Run the plugin
        print(f"Starting manual login test for {account.email}")
        results = await plugin.run(tab, account)
        
        # Display results
        print("\nTest Results:")
        print(json.dumps(results, indent=2))
        
    finally:
        # Cleanup
        await browser_manager.close_all()

if __name__ == "__main__":
    asyncio.run(test_manual_login())