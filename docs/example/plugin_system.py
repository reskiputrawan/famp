"""
Example demonstrating the plugin system for Facebook automation.

This example shows how to:
1. Create a simple plugin system
2. Register and run plugins
3. Define a standard plugin interface
"""
import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

import nodriver as nd


class Plugin:
    """Base class for plugins."""
    
    async def run(self, tab: nd.Tab, account: Dict[str, Any]) -> Dict[str, Any]:
        """Run the plugin.
        
        Args:
            tab: nodriver Tab object
            account: Account credentials and information
            
        Returns:
            Result of the plugin execution
        """
        raise NotImplementedError("Plugins must implement run()")


class LoginPlugin(Plugin):
    """Plugin for Facebook login."""
    
    async def run(self, tab: nd.Tab, account: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Navigate to Facebook
            await tab.get("https://www.facebook.com/")
            print("Navigated to Facebook")
            
            # Check if already logged in
            try:
                await tab.wait_for_selector('[aria-label="Facebook"]', timeout=5000)
                print("Already logged in")
                return {"status": "success", "message": "Already logged in"}
            except:
                print("Not logged in, proceeding with login")
            
            # Fill in email/username
            email_input = await tab.wait_for_selector('input[name="email"]')
            await email_input.type(account["username"])
            
            # Fill in password
            password_input = await tab.wait_for_selector('input[name="pass"]')
            await password_input.type(account["password"])
            
            # Click login button
            login_button = await tab.wait_for_selector('button[name="login"]')
            await login_button.click()
            
            # Wait for navigation to complete
            await tab.wait_for_navigation()
            
            # Check for successful login
            try:
                await tab.wait_for_selector('[aria-label="Facebook"]', timeout=10000)
                print("Login successful")
                return {"status": "success", "message": "Login successful"}
            except:
                print("Login failed")
                return {"status": "error", "message": "Login failed"}
                
        except Exception as e:
            print(f"Login error: {e}")
            return {"status": "error", "message": str(e)}


class ProfileViewerPlugin(Plugin):
    """Plugin for viewing Facebook profiles."""
    
    async def run(self, tab: nd.Tab, account: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Check if profile URL is provided
            profile_url = account.get("profile_url")
            if not profile_url:
                return {"status": "error", "message": "No profile URL provided"}
            
            # Navigate to the profile
            await tab.get(profile_url)
            print(f"Navigated to profile: {profile_url}")
            
            # Wait for profile to load
            try:
                # Wait for cover photo, which indicates profile loaded
                await tab.wait_for_selector('[data-imgperflogname="profileCoverPhoto"]', timeout=10000)
                print("Profile loaded successfully")
                
                # Get profile name
                name_element = await tab.query_selector('h1')
                name = await name_element.text() if name_element else "Unknown"
                
                return {
                    "status": "success", 
                    "message": f"Viewed profile of {name}",
                    "data": {"name": name}
                }
            except Exception as e:
                print(f"Error loading profile: {e}")
                return {"status": "error", "message": f"Error loading profile: {e}"}
                
        except Exception as e:
            print(f"Profile viewer error: {e}")
            return {"status": "error", "message": str(e)}


class PluginManager:
    """Manages plugins for Facebook automation."""
    
    def __init__(self):
        """Initialize the plugin manager."""
        self.plugins: Dict[str, Plugin] = {}
        
    def register_plugin(self, name: str, plugin: Plugin) -> None:
        """Register a plugin.
        
        Args:
            name: Name of the plugin
            plugin: Plugin instance
        """
        self.plugins[name] = plugin
        print(f"Registered plugin: {name}")
        
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name.
        
        Args:
            name: Name of the plugin
            
        Returns:
            Plugin instance or None if not found
        """
        return self.plugins.get(name)
        
    def list_plugins(self) -> List[str]:
        """List all plugin names.
        
        Returns:
            List of plugin names
        """
        return list(self.plugins.keys())


async def main():
    """Run the example."""
    # Initialize plugin manager
    plugin_manager = PluginManager()
    
    # Register plugins
    plugin_manager.register_plugin("login", LoginPlugin())
    plugin_manager.register_plugin("profile", ProfileViewerPlugin())
    
    # List available plugins
    print(f"Available plugins: {plugin_manager.list_plugins()}")
    
    # Setup browser
    account_id = "demo"
    data_dir = Path(f"./data/{account_id}")
    data_dir.mkdir(parents=True, exist_ok=True)
    cookie_path = data_dir / "cookies.pkl"
    
    browser = nd.NoDriver(
        headless=False,
        user_data_dir=str(data_dir),
        incognito=False,
    )
    
    try:
        # Start the browser
        await browser.start()
        tab = await browser.new_tab()
        
        # Load cookies if available
        if cookie_path.exists():
            await tab.cookies.load(str(cookie_path))
        
        # Account information
        print("Enter your Facebook credentials:")
        username = input("Email or Phone: ")
        password = input("Password: ")
        
        account = {
            "username": username,
            "password": password,
        }
        
        # Run the login plugin
        login_plugin = plugin_manager.get_plugin("login")
        result = await login_plugin.run(tab, account)
        print(f"Login result: {result}")
        
        # If login successful, run profile viewer plugin
        if result["status"] == "success":
            # Save cookies
            await tab.cookies.save(str(cookie_path))
            print("Cookies saved")
            
            # Ask for profile URL
            profile_url = input("Enter a Facebook profile URL to view (or press Enter to skip): ")
            
            if profile_url:
                account["profile_url"] = profile_url
                profile_plugin = plugin_manager.get_plugin("profile")
                profile_result = await profile_plugin.run(tab, account)
                print(f"Profile view result: {profile_result}")
        
        # Keep browser open for demonstration
        input("Press Enter to close the browser...")
        
    finally:
        # Clean up
        await browser.close()
        print("Browser closed")


if __name__ == "__main__":
    asyncio.run(main())
