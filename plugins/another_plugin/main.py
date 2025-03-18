"""Implementation for another_plugin plugin."""

import asyncio
import logging

logger = logging.getLogger(__name__)

async def run(context):
    """Run the plugin logic."""
    logger.info("Starting another_plugin plugin")
    
    try:
        # Get browser instance
        logger.info("Starting browser")
        browser = await context.browser_manager.get_browser(
            context.account.account_id,
            headless=False
        )
        
        # Get a tab
        tab = await context.browser_manager.get_tab(context.account.account_id)
        logger.info("Browser tab ready")
        
        # Navigate to example.com
        await tab.goto("https://example.com")
        logger.info("Navigated to example.com")
        
        # Your plugin implementation here
        # ...
        
        # Wait a moment to see the page
        await asyncio.sleep(2)
        
        # Close browser
        await context.browser_manager.close_browser(context.account.account_id)
        logger.info("Plugin execution complete")
        
        return {
            "success": True,
            "message": "another_plugin executed successfully"
        }
    except Exception as e:
        logger.error(f"Plugin execution failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Plugin execution failed"
        }
