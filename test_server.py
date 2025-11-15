#!/usr/bin/env python3
"""
Test Script für MCP Server
"""

import asyncio
from src.providers.oparl_provider import OParlProvider


async def test_oparl_provider():
    """OParl Provider testen"""
    print("🧪 Testing OParl Provider...")
    
    provider = OParlProvider()
    
    try:
        # Test 1: Municipalities laden
        print("\n1. Loading municipalities...")
        municipalities = await provider.get_municipalities()
        print(f"   Found {len(municipalities)} municipalities")
        
        if municipalities:
            first_muni = municipalities[0]
            print(f"   First: {first_muni.name} ({first_muni.id})")
            
            # Test 2: Meetings laden
            print(f"\n2. Loading meetings for {first_muni.name}...")
            meetings = await provider.get_meetings(first_muni.id)
            print(f"   Found {len(meetings)} meetings")
            
            if meetings:
                first_meeting = meetings[0]
                print(f"   First: {first_meeting.name} ({first_meeting.start})")
                
                # Test 3: Meeting Details
                print(f"\n3. Loading meeting details...")
                details = await provider.get_meeting_details(first_meeting.id)
                if details:
                    print(f"   Meeting: {details.name}")
                    print(f"   Agenda items: {len(details.agendaItem or [])}")
                    print(f"   Has protocol: {details.resultsProtocol is not None}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        await provider.close()
        print("\n✅ Test completed")


if __name__ == "__main__":
    asyncio.run(test_oparl_provider())
