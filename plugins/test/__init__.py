"""FAMP plugin: test."""

from famp.plugin import Plugin
from nodriver import Tab
from famp.core.account import FacebookAccount
from typing import Dict, Any

class TestPlugin(Plugin):
    """Plugin for Test."""

    name = "test"
    version = "0.1.0"
    description = "Test"

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
        # Import the run function from main.py
        from .main import run as run_main
        
        # Create a context object with required attributes
        context = type('Context', (), {
            'browser_manager': None,  # We don't need this anymore
            'account': account
        })()
        
        # Since we have direct access to the Tab, we can modify main.py's run function to use it
        context.tab = tab
        return await run_main(context)

# Instantiate the plugin for auto-discovery
plugin = TestPlugin()
