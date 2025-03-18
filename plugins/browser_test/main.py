"""Browser test plugin implementation."""

import asyncio
import logging

logger = logging.getLogger(__name__)

async def run(context):
    """Test the browser lifecycle."""
    logger.info("Testing browser lifecycle")
    
    try:
        # Get browser instance
        logger.info("Starting browser")
        browser = await context.browser_manager.get_browser(
            context.account.account_id, 
            headless=False
        )
        logger.info("Browser started successfully")

        # Navigate to a simple test page
        logger.info("Getting browser tab")
        tab = await context.browser_manager.get_tab(context.account.account_id)
        logger.info("Tab obtained, navigating to example.com")
        
        await tab.get("https://example.com")
        logger.info("Navigation complete")

        # Verify page loaded
        title = await tab.evaluate("document.title")
        logger.info(f"Page loaded with title: {title}")
        
        # Wait a moment to see the page
        logger.info("Waiting 5 seconds before closing browser")
        await asyncio.sleep(5)

        # Close browser
        logger.info("Closing browser")
        await context.browser_manager.close_browser(context.account.account_id)
        logger.info("Browser closed successfully")

        return {
            "success": True, 
            "title": title,
            "message": "Browser test completed successfully"
        }
    except Exception as e:
        logger.error(f"Browser test failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Browser test failed"
        }