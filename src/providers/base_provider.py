"""Base Provider Interface"""

from abc import ABC, abstractmethod
from typing import List, Optional
from ..schemas import Municipality, Meeting


class BaseProvider(ABC):
    """Abstract base class für Datenquellen-Provider"""
    
    @abstractmethod
    async def get_municipalities(self) -> List[Municipality]:
        """Verfügbare Kommunen abrufen"""
        pass
    
    @abstractmethod
    async def get_meetings(
        self, 
        municipality_id: str, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Meeting]:
        """Sitzungen für Kommune abrufen"""
        pass
    
    @abstractmethod
    async def get_meeting_details(self, meeting_id: str) -> Optional[Meeting]:
        """Detaillierte Meeting-Daten abrufen"""
        pass
    
    @abstractmethod
    async def get_protocol_text(self, meeting_id: str) -> Optional[str]:
        """Protokoll-Volltext für LLM abrufen"""
        pass
