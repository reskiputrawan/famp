"""FAMP plugin: another_plugin."""

from famp.plugin import Plugin
from nodriver import Tab
from famp.core.account import FacebookAccount
from typing import Dict, Any

class AnotherPluginPlugin(Plugin):
    """Plugin for Your description here."""

    name = "another_plugin"
    version = "0.1.0"
    description = "Your description here"

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
            'browser_manager': tab._browser_context.browser_instance.browser_manager,
            'account': account
        })()
        
        # Run the main implementation
        return await run_main(context)

# Instantiate the plugin for auto-discovery
plugin = AnotherPluginPlugin()
