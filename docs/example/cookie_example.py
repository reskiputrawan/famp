#!/usr/bin/env python3
"""
Example demonstrating cookie management in FAMP with nodriver.
This shows how to save, load, and manage browser cookies between sessions.
"""

import asyncio
import logging
import os
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path to allow imports from famp
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from famp.core.browser import BrowserManager

async def cookie_demo():
    """Demonstrate cookie management with nodriver."""
    # Create a temporary directory for storing cookies
    temp_dir = Path("/tmp/famp_cookie_demo")
    temp_dir.mkdir(exist_ok=True)
    
    logger.info(f"Using temporary directory: {temp_dir}")
    
    # Initialize browser manager
    browser_manager = BrowserManager(data_dir=temp_dir)
    
    # Configure cookie settings
    browser_manager.cookie_settings.update({
        "use_pickle": True,
        "encryption_enabled": False,  # For simplicity in this demo
        "domain_filter": ["example.com"],
    })
    
    # Account identifier for this demo
    account_id = "demo_account"
    
    try:
        # Start a browser session
        logger.info("Starting browser...")
        browser = await browser_manager.get_browser(account_id)
        
        # Get a tab (main tab by default)
        tab = await browser_manager.get_tab(account_id)
        
        # Visit a website
        logger.info("Visiting example.com...")
        await tab.get("https://example.com")
        
        # Wait for page to load
        await asyncio.sleep(2)
        
        # Save the cookies
        logger.info("Saving cookies...")
        success = await browser_manager.save_cookies(account_id)
        logger.info(f"Cookies saved: {success}")
        
        # Close the browser
        logger.info("Closing browser...")
        await browser_manager.close_browser(account_id)
        
        # Wait a moment
        await asyncio.sleep(1)
        
        # Start a new browser session
        logger.info("Starting new browser session...")
        browser = await browser_manager.get_browser(account_id)
        
        # Get a tab
        tab = await browser_manager.get_tab(account_id)
        
        # Load the cookies
        logger.info("Loading cookies...")
        success = await browser_manager.load_cookies(account_id)
        logger.info(f"Cookies loaded: {success}")
        
        # Visit the website again (should use loaded cookies)
        logger.info("Visiting example.com again with loaded cookies...")
        await tab.get("https://example.com")
        
        # Wait to see the page
        await asyncio.sleep(3)
        
        # Demonstrate other cookie operations
        
        # Create a backup
        logger.info("Creating cookie backup...")
        await browser_manager._create_cookie_backup(account_id)
        
        # Refresh cookies
        logger.info("Refreshing cookies...")
        await browser_manager.refresh_cookies(account_id)
        
        # Clear cookies
        logger.info("Clearing cookies...")
        success = await browser_manager.clear_cookies(account_id)
        logger.info(f"Cookies cleared: {success}")
        
    finally:
        # Clean up
        logger.info("Cleaning up...")
        if hasattr(browser_manager, "browsers"):
            await browser_manager.close_all()
        
        logger.info("Demo completed!")

if __name__ == "__main__":
    asyncio.run(cookie_demo())
