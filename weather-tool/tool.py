"""
MCP Weather Server Tool

This is a Model Context Protocol (MCP) compliant tool that provides weather forecasts.
The server:
1. Advertises its capabilities through a tool description format
2. Implements the 'get-forecast' tool for retrieving weather data
3. Follows the MCP specification for stdin/stdout communication
4. Properly handles errors and returns them in the expected format

This demonstrates the basic structure of an MCP tool that can be called by any
MCP-compatible client, whether it's a CLI tool, API server, or language model.

Usage:
    # Run directly (for testing)
    python server.py
    
    # Then input JSON in MCP format, e.g.:
    {"type":"tool-call","tool":"get-forecast","input":{"location":"Seattle"}}
    
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
    - Weather API: https://wttr.in/ (no API key needed, may have rate limits)
    
Note:
    This tool falls back to mock weather data if the external API is unavailable
    or rate-limited. For production use, consider using a more reliable weather
    service with proper API authentication and error handling.
"""

import sys
import json
import requests
from random import choice

def describe_tools():
    """
    Advertises tool capabilities by outputting a tool description JSON.
    This is the first message sent by an MCP tool upon startup.
    """
    print(json.dumps({
        "type": "tool-description",
        "tools": [
            {
                "name": "get-forecast",
                "description": "Returns the current weather for a location",
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
                        "forecast": { "type": "string" }
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
    if tool == "get-forecast":
        return get_forecast(input["location"])
    return { "forecast": "Unknown tool" }

def get_forecast(location):
    """
    Attempts to fetch real weather data for the given location.
    Falls back to mock data if the API request fails.
    """
    try:
        # Try to get data from a free weather API that doesn't require authentication
        url = f"https://wttr.in/{location}?format=j1"
        response = requests.get(url, timeout=3)
        
        if response.status_code == 200:
            data = response.json()
            temp = data.get("current_condition", [{}])[0].get("temp_F", "??")
            desc = data.get("current_condition", [{}])[0].get("weatherDesc", [{}])[0].get("value", "unknown")
            return {
                "location": location,
                "forecast": f"{desc} and {temp}°F in {location}"
            }
    except:
        # If anything goes wrong, fall back to mock data
        pass
    
    # Mock data as fallback
    conditions = choice(["Sunny", "Cloudy", "Rainy", "Partly cloudy", "Clear skies"])
    temp = choice(range(60, 85))
    return {
        "location": location,
        "forecast": f"{conditions} and {temp}°F in {location}"
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
