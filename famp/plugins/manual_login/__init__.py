"""Manual login plugin for FAMP.

This plugin helps with manual login to Facebook accounts by providing
guidance and verifying login status, but requiring manual user interaction
for sensitive steps like entering credentials and 2FA codes.
"""

from .main import ManualLoginPlugin

# Create plugin instance
plugin = ManualLoginPlugin()