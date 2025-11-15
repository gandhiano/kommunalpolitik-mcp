"""Municipality Schema - basierend auf OParl Body"""

from pydantic import BaseModel
from typing import Optional


class Municipality(BaseModel):
    """OParl Body als Municipality für MCP Client"""
    id: str  # Kurze ID (z.B. "5205")
    name: str
    oparl_url: str  # Vollständige OParl URL
    oparl_endpoint: str
    data_source: str = "oparl"
    last_updated: str  # ISO timestamp
    meeting_list_url: str  # Body.meeting URL
    website: Optional[str] = None
