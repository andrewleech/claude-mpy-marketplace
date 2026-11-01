"""
Provide information about the application and its version.
"""

import os
import sys
import logging

log = logging.getLogger("version")


application_name = "TemplateTestUnix"

unix = sys.platform == "linux"

try:
    # embedded firmware version
    firmware_version = build_tag = os.uname().version
except AttributeError:
    try:
        # unix port support
        import platform

        firmware_version = build_tag = platform.platform()
    except ImportError:
        firmware_version = build_tag = "unknown"
