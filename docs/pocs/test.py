from nodriver import *
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    args = []
    headless = False
    proxy = None
    if headless:
        args.append("--headless=new")
    if proxy:
        args.append(f"--proxy-server={proxy}")

    # Pass variables to start function
    browser = await start(browser_args=args)

    tab = await browser.get("https://example.com")
    # Your automation code here
    browser.stop()

if __name__ == "__main__":
    loop().run_until_complete(main())
