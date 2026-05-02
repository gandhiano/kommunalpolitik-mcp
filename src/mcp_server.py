#!/usr/bin/env python3
"""
Kommunalpolitik MCP Server

Ein MCP Server für deutsche Kommunalpolitik mit OParl API Integration.
Stellt strukturierte Daten für Client-LLMs bereit.
"""

import asyncio
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

from .tools.municipalities import list_municipalities, list_municipalities_tool
from .tools.meetings import (
    get_meetings, get_meetings_tool,
    get_meeting_details, get_meeting_details_tool, 
    get_protocol_text, get_protocol_text_tool
)
from .tools.witzenhausen import (
    get_witzenhausen_document_text,
    get_witzenhausen_document_text_tool,
    get_witzenhausen_evidence_pack,
    get_witzenhausen_evidence_pack_tool,
    get_witzenhausen_meeting,
    get_witzenhausen_meeting_tool,
    find_witzenhausen_actor_topics,
    find_witzenhausen_actor_topics_tool,
    list_witzenhausen_bodies,
    list_witzenhausen_bodies_tool,
    list_witzenhausen_meetings,
    list_witzenhausen_meetings_tool,
    search_witzenhausen_documents,
    search_witzenhausen_documents_tool,
    search_witzenhausen_text,
    search_witzenhausen_text_tool,
)

# Logging konfigurieren - nur für Debugging, nicht in Produktion
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# MCP Server erstellen
server = Server("kommunalpolitik-mcp")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Verfügbare MCP Tools auflisten"""
    return [
        list_municipalities_tool,
        get_meetings_tool,
        get_meeting_details_tool,
        get_protocol_text_tool,
        list_witzenhausen_bodies_tool,
        list_witzenhausen_meetings_tool,
        get_witzenhausen_meeting_tool,
        search_witzenhausen_documents_tool,
        get_witzenhausen_document_text_tool,
        search_witzenhausen_text_tool,
        find_witzenhausen_actor_topics_tool,
        get_witzenhausen_evidence_pack_tool,
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    """MCP Tool aufrufen"""
    
    try:
        if name == "list_municipalities":
            return await list_municipalities()
        
        elif name == "get_meetings":
            return await get_meetings(
                municipality_oparl_url=arguments["municipality_oparl_url"],
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
                page=arguments.get("page"),
                limit=arguments.get("limit")
            )
        
        elif name == "get_meeting_details":
            return await get_meeting_details(
                meeting_oparl_url=arguments["meeting_oparl_url"]
            )
        
        elif name == "get_protocol_text":
            return await get_protocol_text(
                meeting_oparl_url=arguments["meeting_oparl_url"]
            )

        elif name == "list_witzenhausen_bodies":
            return await list_witzenhausen_bodies(
                limit=arguments.get("limit", 100)
            )

        elif name == "list_witzenhausen_meetings":
            return await list_witzenhausen_meetings(
                body_id=arguments.get("body_id"),
                year=arguments.get("year"),
                limit=arguments.get("limit", 20)
            )

        elif name == "get_witzenhausen_meeting":
            return await get_witzenhausen_meeting(
                meeting_id=arguments["meeting_id"]
            )

        elif name == "search_witzenhausen_documents":
            return await search_witzenhausen_documents(
                query=arguments["query"],
                document_type=arguments.get("document_type"),
                limit=arguments.get("limit", 10)
            )

        elif name == "get_witzenhausen_document_text":
            return await get_witzenhausen_document_text(
                document_id=arguments["document_id"]
            )

        elif name == "search_witzenhausen_text":
            return await search_witzenhausen_text(
                query=arguments["query"],
                from_date=arguments.get("from_date"),
                to_date=arguments.get("to_date"),
                body=arguments.get("body"),
                document_type=arguments.get("document_type"),
                limit=arguments.get("limit", 20)
            )

        elif name == "find_witzenhausen_actor_topics":
            return await find_witzenhausen_actor_topics(
                actor=arguments["actor"],
                topic=arguments.get("topic"),
                actor_type=arguments.get("actor_type"),
                from_date=arguments.get("from_date"),
                to_date=arguments.get("to_date"),
                body=arguments.get("body"),
                document_type=arguments.get("document_type", "minutes"),
                confidence=arguments.get("confidence"),
                limit=arguments.get("limit", 30)
            )

        elif name == "get_witzenhausen_evidence_pack":
            return await get_witzenhausen_evidence_pack(
                actor=arguments.get("actor"),
                topic=arguments.get("topic"),
                from_date=arguments.get("from_date"),
                to_date=arguments.get("to_date"),
                body=arguments.get("body"),
                limit=arguments.get("limit", 50)
            )
        
        else:
            raise ValueError(f"Unbekanntes Tool: {name}")
    
    except Exception as e:
        raise


async def main():
    """MCP Server starten"""
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, 
            write_stream, 
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
