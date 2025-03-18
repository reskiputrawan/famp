"""Browser test plugin implementation."""

import asyncio
import logging

logger = logging.getLogger(__name__)

async def run(context):
    """Test the browser lifecycle."""
    logger.info("Testing browser lifecycle")

    try:
        # Use the tab that was passed in
        tab = context.tab
        logger.info("Browser tab ready")

        # Navigate to a simple test page
        logger.info("Navigating to example.com")
        if hasattr(tab, 'goto'):
            await tab.goto("https://example.com")
        else:
            # Try alternate method name
            await tab.get("https://example.com")
        logger.info("Navigation complete")

        # Verify page loaded
        title = await tab.evaluate("document.title")
        logger.info(f"Page loaded with title: {title}")

        # Wait a moment to see the page
        logger.info("Waiting 3 seconds for visual inspection")
        await asyncio.sleep(3)

        # Take screenshot
        # Note: this depends on the Tab implementation having a screenshot method
        # If it doesn't exist, this will cause an error, so we'll catch it
        try:
            screenshot_data = await tab.screenshot()
            logger.info(f"Captured screenshot with {len(screenshot_data)} bytes")
        except (AttributeError, NotImplementedError):
            logger.info("Screenshot functionality not available")

        logger.info("Browser test completed successfully")

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
