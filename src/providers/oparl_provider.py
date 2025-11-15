"""OParl API Provider"""

import aiohttp
import json
import re
from typing import List, Optional
from datetime import datetime
from .base_provider import BaseProvider
from ..schemas import Municipality, Meeting, AgendaItem, File


class OParlProvider(BaseProvider):
    """Provider für OParl API Zugriff"""
    
    def __init__(self, base_url: str = "https://sessionnet-oparl.owl-it.de/oparl"):
        self.base_url = base_url
        self.session = None
    
    def _infer_city_name(self, website_url: str) -> str:
        """Stadtname aus Website-URL extrahieren"""
        if not website_url:
            return "Unbekannt"
        
        # Extrahiere Stadtname aus URL wie "https://sessionnet.owl-it.de/rees/bi"
        match = re.search(r'/([^/]+)/bi/?$', website_url)
        if match:
            city_slug = match.group(1)
            # Konvertiere URL-Slug zu lesbarem Namen
            city_name = city_slug.replace('-', ' ').title()
            
            # Spezielle Fälle korrigieren
            replacements = {
                'Stadt Ahaus': 'Ahaus',
                'Vglandstuhl': 'VG Landstuhl',
                'Kaiserslautern Kreis': 'Landkreis Kaiserslautern',
                'Gruenheide Mark': 'Grünheide (Mark)',
                'Fuerstenwalde Spree': 'Fürstenwalde/Spree',
                'Bad Duerkheim': 'Bad Dürkheim',
                'Woelfersheim': 'Wölfersheim'
            }
            
            return replacements.get(city_name, city_name)
        
        return "Unbekannt"
    
    async def _get_session(self):
        """HTTP Session erstellen"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={
                    'User-Agent': 'Kommunalpolitik-MCP/1.0',
                    'Accept': 'application/json'
                }
            )
        return self.session
    
    async def _make_request(self, url: str) -> Optional[dict]:
        """HTTP Request mit Error Handling"""
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            print(f"Request error for {url}: {e}")
            return None
    
    async def get_municipalities(self) -> List[Municipality]:
        """OParl Bodies als Municipalities laden"""
        system_url = f"{self.base_url}/system"
        system_data = await self._make_request(system_url)
        
        if not system_data:
            return []
        
        bodies_url = system_data.get("body")
        if not bodies_url:
            return []
        
        bodies_data = await self._make_request(bodies_url)
        if not bodies_data or "data" not in bodies_data:
            return []
        
        municipalities = []
        for body in bodies_data["data"]:
            website = body.get("website", "")
            city_name = self._infer_city_name(website)
            
            # Extrahiere nur die ID aus der OParl URL
            oparl_id = body["id"]
            municipality_id = oparl_id.split("/")[-1] if "/" in oparl_id else oparl_id
            
            municipality = Municipality(
                id=municipality_id,  # Nur die ID, nicht die volle URL
                name=city_name,
                oparl_url=oparl_id,  # Vollständige OParl URL für API calls
                oparl_endpoint=self.base_url,
                meeting_list_url=body.get("meeting", ""),
                last_updated=datetime.now().isoformat(),
                website=website
            )
            municipalities.append(municipality)
        
        return municipalities
    
    async def get_meetings(
        self, 
        municipality_id: str, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Meeting]:
        """Meetings für Municipality laden"""
        # Vereinfachte Implementierung - lädt erste Seite
        meetings_url = f"{self.base_url}/bodies/{municipality_id}/meetings"
        
        # Filter hinzufügen wenn vorhanden
        params = []
        if start_date:
            params.append(f"modified_since={start_date}")
        if end_date:
            params.append(f"modified_until={end_date}")
        
        if params:
            meetings_url += "?" + "&".join(params)
        
        meetings_data = await self._make_request(meetings_url)
        if not meetings_data or "data" not in meetings_data:
            return []
        
        meetings = []
        for meeting_data in meetings_data["data"]:
            # Extrahiere Meeting ID aus OParl URL
            oparl_url = meeting_data["id"]
            meeting_id = oparl_url.split("/")[-1] if "/" in oparl_url else oparl_url
            
            meeting = Meeting(
                id=meeting_id,  # Nur die Meeting ID
                oparl_url=oparl_url,  # Vollständige OParl URL
                name=meeting_data.get("name", ""),
                meetingState=meeting_data.get("meetingState"),
                cancelled=meeting_data.get("cancelled", False),
                start=meeting_data.get("start", ""),
                end=meeting_data.get("end"),
                organization=meeting_data.get("organization", []),
                created=meeting_data.get("created", ""),
                modified=meeting_data.get("modified", ""),
                web=meeting_data.get("web")
            )
            meetings.append(meeting)
        
        return meetings
    
    async def get_meeting_details(self, meeting_oparl_url: str) -> Optional[Meeting]:
        """Vollständige Meeting-Details laden"""
        meeting_data = await self._make_request(meeting_oparl_url)
        if not meeting_data:
            return None
        
        # AgendaItems verarbeiten
        agenda_items = []
        if "agendaItem" in meeting_data:
            for item_data in meeting_data["agendaItem"]:
                agenda_item = AgendaItem(
                    id=item_data["id"],
                    number=item_data.get("number"),
                    order=item_data.get("order", 0),
                    name=item_data.get("name", ""),
                    public=item_data.get("public"),
                    consultation=item_data.get("consultation"),
                    result=item_data.get("result"),
                    created=item_data.get("created", ""),
                    modified=item_data.get("modified", "")
                )
                agenda_items.append(agenda_item)
        
        # File-Objekte verarbeiten
        def process_file(file_data):
            if file_data:
                return File(
                    id=file_data["id"],
                    name=file_data.get("name", ""),
                    fileName=file_data.get("fileName"),
                    mimeType=file_data.get("mimeType"),
                    size=file_data.get("size"),
                    accessUrl=file_data.get("accessUrl", ""),
                    downloadUrl=file_data.get("downloadUrl"),
                    created=file_data.get("created", ""),
                    modified=file_data.get("modified", "")
                )
            return None
        
        meeting = Meeting(
            id=meeting_data["id"].split("/")[-1] if "/" in meeting_data["id"] else meeting_data["id"],  # Nur Meeting ID
            oparl_url=meeting_data["id"],  # Vollständige OParl URL
            name=meeting_data.get("name", ""),
            meetingState=meeting_data.get("meetingState"),
            cancelled=meeting_data.get("cancelled", False),
            start=meeting_data.get("start", ""),
            end=meeting_data.get("end"),
            organization=meeting_data.get("organization", []),
            participant=meeting_data.get("participant", []),
            agendaItem=agenda_items if agenda_items else None,
            invitation=process_file(meeting_data.get("invitation")),
            resultsProtocol=process_file(meeting_data.get("resultsProtocol")),
            verbatimProtocol=process_file(meeting_data.get("verbatimProtocol")),
            created=meeting_data.get("created", ""),
            modified=meeting_data.get("modified", ""),
            web=meeting_data.get("web")
        )
        
        return meeting
    
    async def get_protocol_text(self, meeting_oparl_url: str) -> Optional[str]:
        """Protokoll-Text für LLM extrahieren"""
        meeting = await self.get_meeting_details(meeting_oparl_url)
        if not meeting:
            return None
        
        # Priorisiere Wortprotokoll, dann Ergebnisprotokoll
        protocol_file = meeting.verbatimProtocol or meeting.resultsProtocol
        if not protocol_file:
            return None
        
        # Text aus File-Objekt laden (vereinfacht)
        if protocol_file.text:
            return protocol_file.text
        
        # TODO: PDF/HTML Text-Extraktion implementieren
        return f"Protokoll verfügbar unter: {protocol_file.accessUrl}"
    
    async def close(self):
        """Session schließen"""
        if self.session:
            await self.session.close()
