"""Meeting Tools"""

from mcp import Tool
from mcp.types import TextContent
from ..providers import OParlProvider
import json
from typing import Optional


async def get_meetings(
    municipality_oparl_url: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> list[TextContent]:
    """Sitzungen für Kommune abrufen"""
    provider = OParlProvider()
    
    try:
        meetings = await provider.get_meetings(municipality_oparl_url, start_date, end_date)
        
        result = {
            "municipality_oparl_url": municipality_oparl_url,
            "meetings": [
                {
                    "id": m.id,
                    "oparl_url": m.oparl_url,
                    "name": m.name,
                    "start": m.start,
                    "end": m.end,
                    "meetingState": m.meetingState,
                    "cancelled": m.cancelled,
                    "web": m.web
                }
                for m in meetings
            ],
            "total": len(meetings)
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2, ensure_ascii=False)
        )]
    
    finally:
        await provider.close()


async def get_meeting_details(meeting_oparl_url: str) -> list[TextContent]:
    """Detaillierte Meeting-Informationen abrufen"""
    provider = OParlProvider()
    
    try:
        meeting = await provider.get_meeting_details(meeting_oparl_url)
        
        if not meeting:
            return [TextContent(
                type="text",
                text=json.dumps({"error": "Meeting nicht gefunden"}, ensure_ascii=False)
            )]
        
        result = {
            "meeting": {
                "id": meeting.id,
                "oparl_url": meeting.oparl_url,
                "name": meeting.name,
                "start": meeting.start,
                "end": meeting.end,
                "meetingState": meeting.meetingState,
                "cancelled": meeting.cancelled,
                "organization": meeting.organization,
                "participant": meeting.participant,
                "agendaItems": [
                    {
                        "id": item.id,
                        "number": item.number,
                        "order": item.order,
                        "name": item.name,
                        "public": item.public,
                        "result": item.result
                    }
                    for item in (meeting.agendaItem or [])
                ],
                "protocols": {
                    "invitation": meeting.invitation.dict() if meeting.invitation else None,
                    "resultsProtocol": meeting.resultsProtocol.dict() if meeting.resultsProtocol else None,
                    "verbatimProtocol": meeting.verbatimProtocol.dict() if meeting.verbatimProtocol else None
                },
                "web": meeting.web
            }
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2, ensure_ascii=False)
        )]
    
    finally:
        await provider.close()


async def get_protocol_text(meeting_oparl_url: str) -> list[TextContent]:
    """Protokoll-Volltext für LLM-Analyse abrufen"""
    provider = OParlProvider()
    
    try:
        protocol_text = await provider.get_protocol_text(meeting_oparl_url)
        
        if not protocol_text:
            return [TextContent(
                type="text",
                text=json.dumps({"error": "Kein Protokoll verfügbar"}, ensure_ascii=False)
            )]
        
        result = {
            "meeting_oparl_url": meeting_oparl_url,
            "protocol_text": protocol_text,
            "length": len(protocol_text)
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2, ensure_ascii=False)
        )]
    
    finally:
        await provider.close()


# MCP Tool Definitions
get_meetings_tool = Tool(
    name="get_meetings",
    description="Sitzungen für eine Kommune abrufen, optional mit Datumsfilter",
    inputSchema={
        "type": "object",
        "properties": {
            "municipality_oparl_url": {
                "type": "string",
                "description": "OParl URL der Kommune (aus list_municipalities)"
            },
            "start_date": {
                "type": "string",
                "description": "Startdatum (ISO format, optional)"
            },
            "end_date": {
                "type": "string", 
                "description": "Enddatum (ISO format, optional)"
            }
        },
        "required": ["municipality_oparl_url"]
    }
)

get_meeting_details_tool = Tool(
    name="get_meeting_details",
    description="Detaillierte Informationen zu einer Sitzung inkl. Tagesordnung und Protokolle",
    inputSchema={
        "type": "object",
        "properties": {
            "meeting_oparl_url": {
                "type": "string",
                "description": "OParl URL der Sitzung (aus get_meetings)"
            }
        },
        "required": ["meeting_oparl_url"]
    }
)

get_protocol_text_tool = Tool(
    name="get_protocol_text",
    description="Protokoll-Volltext für LLM-Analyse abrufen",
    inputSchema={
        "type": "object",
        "properties": {
            "meeting_oparl_url": {
                "type": "string",
                "description": "OParl URL der Sitzung"
            }
        },
        "required": ["meeting_oparl_url"]
    }
)
