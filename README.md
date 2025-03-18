# FAMP: Facebook Account Management Platform

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

## Development

This project is currently in POC phase.
