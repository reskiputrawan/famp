"""Implementation for test plugin."""

import asyncio
import logging

logger = logging.getLogger(__name__)

async def run(context):
    """Run the plugin logic."""
    logger.info("Starting test plugin")
    
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
        
        # Your plugin implementation here
        # ...
        
        # Wait a moment to see the page
        logger.info("Waiting 3 seconds for visual inspection") 
        await asyncio.sleep(3)
        
        # Take screenshot (if available)
        try:
            screenshot_data = await tab.screenshot()
            logger.info(f"Captured screenshot with {len(screenshot_data)} bytes")
        except (AttributeError, NotImplementedError):
            logger.info("Screenshot functionality not available")
        
        logger.info("Plugin execution complete")
        
        return {
            "success": True,
            "title": title,
            "message": "test executed successfully"
        }
    except Exception as e:
        logger.error(f"Plugin execution failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Plugin execution failed"
        }
