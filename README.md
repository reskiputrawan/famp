# FAMP - Facebook Account Management Platform

A scalable automation platform for managing multiple Facebook accounts using `nodriver`.

## Features

- Browser management with nodriver
- Multiple account management
- Cookie persistence
- Plugin system

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/famp.git
cd famp

# Install dependencies
pip install -e .
```

```
pip install -r requirements.txt
```

## Usage

```bash
# Run with default configuration
python -m famp

# Manage accounts
python -m famp account list
python -m famp account add
python -m famp account remove

# Run specific plugins
python -m famp plugin login -a account_name
```

```
python main.py [OPTIONS] COMMAND [ARGS]...
```

### Global Options

- `--debug/--no-debug`: Enable debug mode with verbose logging
- `--headless/--no-headless`: Run browser in headless/visible mode (default: headless)
- `-h, --help`: Show this help message
- `--version`: Show the version and exit

### Available Commands

- `login`: Automate Facebook login process
- `scroll`: Scroll through Facebook feed and collect posts
- `publish`: Publish posts to Facebook

### Examples

Login to Facebook:

```
python main.py login
```

Scroll through feed:

```
python main.py scroll
```

Publish a post:

```
python main.py publish
```

## Cookie Management

FAMP uses pickle format to save browser cookies with nodriver, providing seamless session persistence:

```python
# Example of working with cookies programmatically
async def save_and_load_cookies():
    browser_manager = BrowserManager()
    
    # Get browser for an account
    browser = await browser_manager.get_browser("account_name")
    
    # Navigation happens here...
    
    # Save cookies for later
    await browser_manager.save_cookies("account_name")
    
    # In another session, load the cookies
    await browser_manager.load_cookies("account_name")
```

Configure cookie settings in your YAML config:

```yaml
browser:
  cookies:
    use_pickle: true  # Recommended for nodriver compatibility
    encryption_enabled: true
    domain_filter:
      - facebook.com
      - fb.com
```

## Development

This project is currently in POC phase.

Using uv:

```
uv run main.py [OPTIONS] COMMAND [ARGS]...
```
