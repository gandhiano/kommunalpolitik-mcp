"""Meeting Schemas - OParl 1.1 konform"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class File(BaseModel):
    """OParl File Schema"""
    id: str
    type: str = "https://schema.oparl.org/1.1/File"
    name: str
    fileName: Optional[str] = None
    mimeType: Optional[str] = None
    size: Optional[int] = None
    accessUrl: str
    downloadUrl: Optional[str] = None
    text: Optional[str] = None  # Extrahierter Text für LLM
    created: str
    modified: str


class AgendaItem(BaseModel):
    """OParl AgendaItem Schema"""
    id: str
    type: str = "https://schema.oparl.org/1.1/AgendaItem"
    meeting: Optional[str] = None  # Meeting URL (nur bei einzelnem Abruf)
    number: Optional[str] = None  # "10.1", "C", etc.
    order: int  # Position in Meeting
    name: str  # Thema
    public: Optional[bool] = None
    consultation: Optional[str] = None  # Consultation URL
    result: Optional[str] = None  # Ergebnis
    created: str
    modified: str


class Meeting(BaseModel):
    """OParl Meeting Schema"""
    id: str  # Meeting ID (z.B. "9918")
    oparl_url: str  # Vollständige OParl URL
    type: str = "https://schema.oparl.org/1.1/Meeting"
    name: str
    meetingState: Optional[str] = None  # "terminiert" | "eingeladen" | "durchgeführt"
    cancelled: Optional[bool] = None
    start: str  # ISO datetime
    end: Optional[str] = None  # ISO datetime
    organization: Optional[List[str]] = None  # Organization URLs
    participant: Optional[List[str]] = None  # Person URLs
    agendaItem: Optional[List[AgendaItem]] = None  # Embedded AgendaItems
    invitation: Optional[File] = None  # File object
    resultsProtocol: Optional[File] = None  # File object
    verbatimProtocol: Optional[File] = None  # File object
    created: str
    modified: str
    web: Optional[str] = None  # Web URL
