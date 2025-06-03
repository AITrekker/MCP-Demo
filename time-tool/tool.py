"""
MCP Time Server Tool

This is a Model Context Protocol (MCP) compliant tool that provides current time information.
The server:
1. Advertises its capabilities through a tool description format
2. Implements the 'get-time' tool for retrieving time data for any location
3. Follows the MCP specification for stdin/stdout communication
4. Properly handles errors and returns them in the expected format

This demonstrates the basic structure of an MCP tool that can be called by any
MCP-compatible client, whether it's a CLI tool, API server, or language model.

Usage:
    # Run directly (for testing)
    python server.py
    
    # Then input JSON in MCP format, e.g.:
    {"type":"tool-call","tool":"get-time","input":{"location":"New York"}}
    
    # Typically this server is called by an MCP client rather than directly
    
    # In this Docker demo, the bridge service calls this tool via subprocess

Architecture in MCP-Demo:
    Browser → Frontend Container → Bridge Container → MCP Tool (this file)
    
    The bridge service (bridge.py) executes this script as a subprocess and
    communicates via stdin/stdout using the MCP protocol format.

Reference:
    For more information about the Model Context Protocol, see:
    https://modelcontextprotocol.io/
    
    APIs used:
    - Geocoding: https://nominatim.openstreetmap.org/ (no API key needed)
    - Time API: https://timeapi.io/ (may have rate limits, falls back to UTC)
    
Note:
    This tool falls back to UTC time if the external APIs are unavailable
    or rate-limited. For production use, consider using a more reliable
    timezone service or implementing local timezone data.
"""

import sys
import json
import datetime
import requests

# Nominatim requires a User-Agent header
HEADERS = {
    "User-Agent": "MCP-TimeServer/1.0"
}

def describe_tools():
    """
    Advertises tool capabilities by outputting a tool description JSON.
    This is the first message sent by an MCP tool upon startup.
    """
    print(json.dumps({
        "type": "tool-description",
        "tools": [
            {
                "name": "get-time",
                "description": "Returns the current time for any location in the world",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": { "type": "string" }
                    },
                    "required": ["location"]
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "location": { "type": "string" },
                        "timezone": { "type": "string" },
                        "time": { "type": "string" },
                        "date": { "type": "string" }
                    }
                }
            }
        ]
    }), flush=True)  # flush ensures immediate output

def handle_call(tool, input):
    """
    Routes incoming tool calls to the appropriate handler function.
    Returns an error message if an unknown tool is requested.
    """
    if tool == "get-time":
        return get_time(input["location"])
    return { "error": "Unknown tool" }

def get_coordinates(location):
    """
    Use OpenStreetMap Nominatim to convert a city name into (lat, lon).
    Returns None if location not found.
    """
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": location,
            "format": "json",
            "limit": 1
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        if not data:
            return None
            
        lat = data[0]["lat"]
        lon = data[0]["lon"]
        return lat, lon
    except Exception:
        return None

def get_time_by_coordinates(lat, lon):
    """
    Call TimeAPI.io's /Time/current/coordinate endpoint to get time info.
    Returns (datetime_str, timezone_id) or (None, None) if error.
    """
    try:
        url = "https://timeapi.io/api/Time/current/coordinate"
        params = {
            "latitude": lat,
            "longitude": lon
        }
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        current_dt = data.get("dateTime")
        tz_id = data.get("timeZone")
        
        if not current_dt or not tz_id:
            return None, None
            
        return current_dt, tz_id
    except Exception:
        return None, None

def get_time(location):
    """
    Gets the current time for the specified location.
    Uses TimeAPI.io approach from time.py.
    """
    try:
        # Step 1: Get coordinates for the location
        coords = get_coordinates(location)
        
        if not coords:
            raise ValueError(f"Location '{location}' not found.")
            
        lat, lon = coords
            
        # Step 2: Get time data from TimeAPI.io
        current_time, timezone_id = get_time_by_coordinates(lat, lon)
        
        if not current_time or not timezone_id:
            raise ValueError("Could not get time data for the coordinates.")
        
        # Format the time data
        dt = datetime.datetime.fromisoformat(current_time.replace('Z', '+00:00'))
        
        return {
            "location": location,
            "timezone": timezone_id,
            "time": dt.strftime("%H:%M:%S"),
            "date": dt.strftime("%Y-%m-%d")
        }
    except ValueError as e:
        # If we can't get the time, return an informative error
        now = datetime.datetime.utcnow()
        return {
            "location": location,
            "timezone": f"Error: {str(e)}",
            "time": now.strftime("%H:%M:%S") + " (UTC)",
            "date": now.strftime("%Y-%m-%d")
        }
    except Exception:
        # Generic error fallback
        now = datetime.datetime.utcnow()
        return {
            "location": location,
            "timezone": "Error: Could not determine time for this location",
            "time": now.strftime("%H:%M:%S") + " (UTC)",
            "date": now.strftime("%Y-%m-%d")
        }

def main():
    """
    Main execution loop that:
    1. Outputs tool description
    2. Processes incoming tool calls from stdin
    3. Returns results in MCP format
    4. Handles errors appropriately
    """
    # 1) Output tool description as first action
    describe_tools()

    # 2) Enter main processing loop for incoming requests
    for line in sys.stdin:
        try:
            # 3) Parse the incoming JSON message
            msg = json.loads(line)
            if msg.get("type") == "tool-call":
                # 4) Handle the tool call
                output = handle_call(msg["tool"], msg["input"])
                # 5) Return the result in MCP format
                print(json.dumps({
                    "type": "tool-result",
                    "output": output
                }), flush=True)
        except Exception as e:
            # 6) Handle any errors in MCP format
            print(json.dumps({
                "type": "error",
                "error": str(e)
            }), flush=True)

if __name__ == "__main__":
    main()
