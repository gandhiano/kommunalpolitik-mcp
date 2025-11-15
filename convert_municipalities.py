#!/usr/bin/env python3
"""
Municipality Data Converter

This script converts OParl municipality data from multiple sources into a unified
municipalities.json file for the MCP server. It aggregates data from:

1. SessionNet OParl endpoint (oparl_resolved_bodies.json)
2. Politik-bei-uns processed data (politik_bei_uns_exploration.json)  
3. OParl endpoints registry (resources/endpoints.yml)

Usage:
    python convert_municipalities.py

Output:
    src/data/municipalities.json - Static municipality database for fast MCP responses

Note: This is a helper script for data aggregation. Run when updating municipality
data or adding new OParl endpoints.
"""

import json
import yaml
from datetime import datetime

def convert_oparl_data():
    """Convert all available OParl data to municipalities.json"""
    
    # Load sessionnet data
    with open('/Users/gualterbaptista/git/politik/kommunal-mcp/oparl_resolved_bodies.json', 'r') as f:
        sessionnet_data = json.load(f)
    
    # Load politik-bei-uns data  
    with open('/Users/gualterbaptista/git/politik/kommunal-mcp/politik_bei_uns_exploration.json', 'r') as f:
        pbu_data = json.load(f)
    
    # Load endpoints.yml data
    with open('/Users/gualterbaptista/git/politik/resources/endpoints.yml', 'r') as f:
        endpoints_data = yaml.safe_load(f)
    
    municipalities = []
    seen_urls = set()  # Avoid duplicates
    
    # Convert sessionnet data
    for body in sessionnet_data["resolved_bodies"]:
        municipality = {
            "id": body["id"],
            "name": body["inferred_city_name"],
            "oparl_url": body["oparl_id"],
            "oparl_endpoint": "https://sessionnet-oparl.owl-it.de/oparl",
            "data_source": "oparl",
            "website": body.get("website", "")
        }
        municipalities.append(municipality)
        seen_urls.add(body["oparl_id"])
    
    # Convert politik-bei-uns data
    for body in pbu_data["all_bodies"]:
        if body["id"] not in seen_urls:
            municipality = {
                "id": body["id"].split("/")[-1],
                "name": body["name"],
                "oparl_url": body["id"],
                "oparl_endpoint": "https://oparl.politik-bei-uns.de",
                "data_source": "oparl",
                "website": body.get("website", "")
            }
            municipalities.append(municipality)
            seen_urls.add(body["id"])
    
    # Convert endpoints.yml data
    for endpoint in endpoints_data:
        if endpoint.get("url") and endpoint["url"] not in seen_urls:
            # Extract endpoint base and create municipality
            oparl_url = endpoint["url"]
            if "/system" in oparl_url:
                oparl_endpoint = oparl_url.replace("/system", "")
            else:
                oparl_endpoint = oparl_url
            
            # Generate ID from title or URL
            title = endpoint.get("title", "Unknown")
            municipality_id = title.lower().replace(" ", "-").replace("stadt-", "").replace("gemeinde-", "")
            
            municipality = {
                "id": municipality_id,
                "name": title,
                "oparl_url": oparl_url,
                "oparl_endpoint": oparl_endpoint,
                "data_source": "oparl",
                "website": ""
            }
            municipalities.append(municipality)
            seen_urls.add(oparl_url)
    
    # Create final structure
    result = {
        "last_updated": datetime.now().isoformat(),
        "total_municipalities": len(municipalities),
        "municipalities": municipalities
    }
    
    # Write to municipalities.json
    with open('src/data/municipalities.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Converted {len(municipalities)} municipalities")
    print(f"   - SessionNet: {len(sessionnet_data['resolved_bodies'])}")
    print(f"   - Politik-bei-uns: {len(pbu_data['all_bodies'])}")
    print(f"   - Endpoints.yml: {len(endpoints_data)}")
    print(f"   - Total unique: {len(municipalities)}")

if __name__ == "__main__":
    convert_oparl_data()
