"""
Legacy import file to maintain backwards compatibility.
This file is deprecated and will be removed in a future version.
Please use famp.cli.__init__ directly instead.
"""

import warnings

warnings.warn(
    "Importing from famp.cli is deprecated. "
    "Please use famp.cli.__init__ instead.",
    DeprecationWarning,
    stacklevel=2
)

from famp.cli.__init__ import cli, main

# Re-export pass_context and handle_error for compatibility
from famp.cli.utils import pass_context, handle_error
