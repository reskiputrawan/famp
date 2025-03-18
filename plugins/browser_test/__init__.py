"""Browser test plugin for FAMP."""

from famp.plugin import Plugin
from nodriver import Tab
from famp.core.account import FacebookAccount
from typing import Dict, Any

class BrowserTestPlugin(Plugin):
    """Plugin that tests basic browser functionality."""

    name = "browser_test"
    version = "0.1.0"
    description = "Tests basic browser functionality including startup and shutdown"

    @property
    def requires(self):
        """No dependencies required."""
        return []
        
    async def run(self, tab: Tab, account: FacebookAccount) -> Dict[str, Any]:
        """Run the plugin.

        Args:
            tab: Browser tab
            account: Facebook account

        Returns:
            Results dictionary
        """
        # We'll directly implement the browser test here
        from .main import run as run_main

        # Create a simple context object that we can pass to the run function
        context = type('Context', (), {
            'browser_manager': None,  # We don't need this anymore
            'account': account
        })()

        # Since we have direct access to the Tab, we can modify main.py's run function to use it
        context.tab = tab

        # Run the main implementation with await
        result = await run_main(context)
        return result

# Instantiate the plugin for auto-discovery
plugin = BrowserTestPlugin()
