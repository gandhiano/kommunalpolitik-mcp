#!/usr/bin/env python3
"""
Kommunalpolitik MCP Server

Lokaler MCP Server für kommunalpolitische Daten.
"""

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

from .tools.witzenhausen import (
    find_actor_topics,
    find_actor_topics_tool,
    get_document_text,
    get_document_text_tool,
    get_evidence_pack,
    get_evidence_pack_tool,
    get_meeting,
    get_meeting_tool,
    list_bodies,
    list_bodies_tool,
    list_meetings,
    list_meetings_tool,
    search_documents,
    search_documents_tool,
    search_text,
    search_text_tool,
)

# MCP Server erstellen
server = Server("kommunalpolitik-mcp")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Verfügbare MCP Tools auflisten"""
    return [
        list_bodies_tool,
        list_meetings_tool,
        get_meeting_tool,
        search_documents_tool,
        get_document_text_tool,
        search_text_tool,
        find_actor_topics_tool,
        get_evidence_pack_tool,
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    """MCP Tool aufrufen"""
    
    try:
        if name == "list_bodies":
            return await list_bodies(
                limit=arguments.get("limit", 100)
            )

        elif name == "list_meetings":
            return await list_meetings(
                body_id=arguments.get("body_id"),
                year=arguments.get("year"),
                limit=arguments.get("limit", 20)
            )

        elif name == "get_meeting":
            return await get_meeting(
                meeting_id=arguments["meeting_id"]
            )

        elif name == "search_documents":
            return await search_documents(
                query=arguments["query"],
                document_type=arguments.get("document_type"),
                limit=arguments.get("limit", 10)
            )

        elif name == "get_document_text":
            return await get_document_text(
                document_id=arguments["document_id"]
            )

        elif name == "search_text":
            return await search_text(
                query=arguments["query"],
                from_date=arguments.get("from_date"),
                to_date=arguments.get("to_date"),
                body=arguments.get("body"),
                document_type=arguments.get("document_type"),
                limit=arguments.get("limit", 20)
            )

        elif name == "find_actor_topics":
            return await find_actor_topics(
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

        elif name == "get_evidence_pack":
            return await get_evidence_pack(
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
