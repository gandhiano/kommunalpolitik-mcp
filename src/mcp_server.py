#!/usr/bin/env python3
"""
Kommunalpolitik MCP Server

Ein MCP Server für deutsche Kommunalpolitik mit OParl API Integration.
Stellt strukturierte Daten für Client-LLMs bereit.
"""

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import Tool

from .tools.municipalities import list_municipalities, list_municipalities_tool
from .tools.meetings import (
    get_meetings, get_meetings_tool,
    get_meeting_details, get_meeting_details_tool, 
    get_protocol_text, get_protocol_text_tool
)


# MCP Server erstellen
server = Server("kommunalpolitik-mcp")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Verfügbare MCP Tools auflisten"""
    return [
        list_municipalities_tool,
        get_meetings_tool,
        get_meeting_details_tool,
        get_protocol_text_tool
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    """MCP Tool aufrufen"""
    
    if name == "list_municipalities":
        return await list_municipalities()
    
    elif name == "get_meetings":
        return await get_meetings(
            municipality_oparl_url=arguments["municipality_oparl_url"],
            start_date=arguments.get("start_date"),
            end_date=arguments.get("end_date")
        )
    
    elif name == "get_meeting_details":
        return await get_meeting_details(
            meeting_oparl_url=arguments["meeting_oparl_url"]
        )
    
    elif name == "get_protocol_text":
        return await get_protocol_text(
            meeting_oparl_url=arguments["meeting_oparl_url"]
        )
    
    else:
        raise ValueError(f"Unbekanntes Tool: {name}")


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
