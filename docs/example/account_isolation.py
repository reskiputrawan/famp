"""
Example demonstrating account isolation with nodriver.

This example shows how to:
1. Create separate browser instances for different accounts
2. Manage cookies for each account separately
3. Ensure sessions don't interfere with each other
"""
import asyncio
import os
from pathlib import Path

import nodriver as nd


async def setup_account(account_id, username, password):
    """Set up a browser instance for an account."""
    print(f"Setting up account: {account_id}")
    
    # Create data directory for this account
    data_dir = Path(f"./data/{account_id}")
    data_dir.mkdir(parents=True, exist_ok=True)
    cookie_path = data_dir / "cookies.pkl"
    
    # Create a browser instance with unique data directory
    browser = nd.NoDriver(
        headless=False,
        user_data_dir=str(data_dir),
        incognito=False,  # Need persistent storage
    )
    
    try:
        # Start the browser
        await browser.start()
        print(f"Started browser for {account_id}")
        
        # Open a new tab
        tab = await browser.new_tab()
        
        # Try to load cookies if they exist
        if cookie_path.exists():
            try:
                await tab.cookies.load(str(cookie_path))
                print(f"Loaded cookies for {account_id}")
            except Exception as e:
                print(f"Error loading cookies for {account_id}: {e}")
        
        # Navigate to Facebook
        await tab.get("https://www.facebook.com")
        
        # Check if already logged in
        try:
            # Look for an element that indicates we're logged in
            await tab.wait_for_selector('[aria-label="Facebook"]', timeout=5000)
            print(f"{account_id} is already logged in")
        except:
            print(f"{account_id} is not logged in, proceeding with login")
            
            # Fill in email/username
            email_input = await tab.wait_for_selector('input[name="email"]')
            await email_input.type(username)
            
            # Fill in password
            password_input = await tab.wait_for_selector('input[name="pass"]')
            await password_input.type(password)
            
            # Click login button
            login_button = await tab.wait_for_selector('button[name="login"]')
            await login_button.click()
            
            # Wait for navigation to complete
            await tab.wait_for_navigation()
            
            # Check for successful login
            try:
                await tab.wait_for_selector('[aria-label="Facebook"]', timeout=10000)
                print(f"{account_id} login successful")
            except:
                print(f"{account_id} login failed")
        
        # Save cookies for future use
        await tab.cookies.save(str(cookie_path))
        print(f"Saved cookies for {account_id}")
        
        # Keep the browser open for demonstration
        print(f"Browser for {account_id} is now ready. Press Enter to close...")
        return browser, tab
    
    except Exception as e:
        print(f"Error setting up {account_id}: {e}")
        await browser.close()
        raise


async def main():
    """Run the example."""
    # Setup account information
    accounts = [
        {
            "id": "account1",
            "username": "your_email1@example.com",
            "password": "your_password1"
        },
        {
            "id": "account2",
            "username": "your_email2@example.com",
            "password": "your_password2"
        }
    ]
    
    # Prompt for credentials if needed
    for i, account in enumerate(accounts):
        if account["username"] == f"your_email{i+1}@example.com":
            print(f"Enter credentials for {account['id']}:")
            username = input("Email or Phone: ")
            password = input("Password: ")
            account["username"] = username
            account["password"] = password
    
    # Set up browsers for each account
    browsers = []
    tasks = []
    
    try:
        # Start all browsers concurrently
        for account in accounts:
            task = asyncio.create_task(
                setup_account(account["id"], account["username"], account["password"])
            )
            tasks.append(task)
        
        # Wait for all browsers to be set up
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Store successful browser setups
        for result in results:
            if isinstance(result, tuple):
                browser, tab = result
                browsers.append(browser)
        
        # Keep browsers open until user presses Enter
        input("Press Enter to close all browsers...")
        
    finally:
        # Clean up all browsers
        for browser in browsers:
            await browser.close()
        
        print("All browsers closed")


if __name__ == "__main__":
    asyncio.run(main())
