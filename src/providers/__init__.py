"""Data Providers für verschiedene Datenquellen"""

from .base_provider import BaseProvider
from .oparl_provider import OParlProvider

__all__ = ["BaseProvider", "OParlProvider"]
