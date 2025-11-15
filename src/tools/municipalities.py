"""Municipality Tools"""

from mcp import Tool
from mcp.types import TextContent
from ..providers import OParlProvider
import json


async def list_municipalities() -> list[TextContent]:
    """Verfügbare Kommunen auflisten"""
    provider = OParlProvider()
    
    try:
        municipalities = await provider.get_municipalities()
        
        result = {
            "municipalities": [
                {
                    "id": m.id,
                    "name": m.name,
                    "data_source": m.data_source,
                    "website": m.website
                }
                for m in municipalities
            ],
            "total": len(municipalities)
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2, ensure_ascii=False)
        )]
    
    finally:
        await provider.close()


# MCP Tool Definition
list_municipalities_tool = Tool(
    name="list_municipalities",
    description="Liste aller verfügbaren Kommunen mit OParl API Zugang",
    inputSchema={
        "type": "object",
        "properties": {},
        "required": []
    }
)
