from nodriver import loop, Browser, Tab, start

async def run(context):
  print("Starting first browser instance...")
  browser = await start()
  print(f"Browser started: {browser}")

  print("Navigating to Google...")
  tab = await browser.get("https://google.com")
  print(f"Tab created: {tab}")

  print("Saving cookies to /tmp/cookies.pkl...")
  cookies = await browser.cookies.save("/tmp/cookies.pkl")
  print(f"Cookies saved: {cookies}")

  print("Stopping first browser...")
  browser.stop()
  print("First browser stopped")

  print("\nStarting second browser instance...")
  browser = await start()
  print(f"Second browser started: {browser}")

  print("Loading cookies from /tmp/cookies.pkl...")
  await browser.cookies.load("/tmp/cookies.pkl")
  print("Cookies loaded")

  print("Navigating to Google with loaded cookies...")
  tab = await browser.get("https://google.com")
  print(f"Tab created: {tab}")

  print(f"Waiting for 3 seconds...")
  await tab.wait(3)
  print("Wait completed")

  print("Stopping second browser...")
  browser.stop()
  print("Second browser stopped")

if __name__ == "__main__":
  print("Script starting...")
  loop().run_until_complete(run(None))
  print("Script completed")
