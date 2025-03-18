# Manual Login Plugin

A FAMP plugin that guides users through a manual Facebook login process while providing verification and guidance.

## Purpose

This plugin is designed for situations where automated login might not be reliable or desired, such as:

- Accounts that frequently encounter security checkpoints
- First-time logins on new devices/IP addresses
- Accounts with advanced security settings
- When troubleshooting login issues

## Features

- **Manual Interaction**: User completes the login process manually
- **Auto-Detection**: Detects login status, checkpoint pages, and success
- **Configurable**: Options for auto-filling credentials (email/password)
- **Status Verification**: Confirms whether login was successful
- **Checkpoint Handling**: Detects and waits during two-factor and other security checkpoints

## Usage

Run the plugin with:

```bash
famp plugin run manual_login ACCOUNT_ID --no-headless
```

The `--no-headless` flag is required to make the browser visible for manual interaction.

## Configuration

Create a JSON configuration file with the following options:

```json
{
  "wait_timeout": 300,
  "check_interval": 5,
  "auto_fill_email": true,
  "auto_fill_password": false,
  "skip_if_logged_in": true
}
```

| Option | Description | Default |
|--------|-------------|---------|
| `wait_timeout` | Maximum time to wait for login completion (seconds) | 300 |
| `check_interval` | How often to check login status (seconds) | 5 |
| `auto_fill_email` | Whether to auto-fill the email address | true |
| `auto_fill_password` | Whether to auto-fill the password (disabled by default for security) | false |
| `skip_if_logged_in` | Skip login process if already logged in | true |

## Example

```bash
# Run the plugin with the default configuration
famp plugin run manual_login my_account --no-headless

# Run the plugin with a custom configuration file
famp plugin run manual_login my_account --no-headless --config manual_login_config.json
```

## Security Notes

- Password auto-fill is disabled by default for security reasons
- Consider using this plugin when security is more important than automation
- Always ensure you're using the plugin in a secure environment
