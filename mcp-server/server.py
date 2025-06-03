"""
MCP Server

This Flask-based HTTP server acts as an intermediary between web browsers
and Model Context Protocol (MCP) tools. It provides a REST API interface that
translates HTTP requests into MCP protocol calls.

Architecture:
    Browser → HTTP Request → MCP Server → MCP Tool → HTTP Response → Browser
    
    The MCP server:
    1. Receives HTTP POST requests with JSON payloads
    2. Translates them into MCP protocol format
    3. Executes MCP tools as subprocesses via stdin/stdout
    4. Parses MCP tool responses and returns them as HTTP JSON responses
    5. Handles CORS to allow browser access from different origins

Endpoints:
    POST /weather - Get weather forecast for a location
    POST /time    - Get current time for a location

Usage in MCP_Docker-Demo:
    This service runs in a Docker container and is called by the frontend
    container's JavaScript code. It serves as the MCP server that hosts
    and executes MCP tools.

    Frontend (mcp_host.html) → MCP Server (this file) → MCP Tools (weather/time tools)

Docker Integration:
    - Runs on port 5000 inside the mcp-server container
    - Exposed to host machine via docker-compose port mapping
    - Contains weather-tool and time-tool Python scripts
    - Executes MCP tools as subprocesses within the same container

Protocol Translation:
    HTTP Request:  {"location": "Seattle"}
    MCP Format:    {"type": "tool-call", "tool": "get-forecast", "input": {"location": "Seattle"}}
    MCP Response:  {"type": "tool-result", "output": {"location": "Seattle", "forecast": "..."}}
    HTTP Response: {"location": "Seattle", "forecast": "..."}

Reference:
    For more information about the Model Context Protocol, see:
    https://modelcontextprotocol.io/
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import json

app = Flask(__name__)
CORS(app)  # Enable CORS for browser access from different origins

def call_mcp_tool(tool_path, tool_name, input_data):
    """
    Execute an MCP tool as a subprocess and parse its response.
    
    Args:
        tool_path (str): Path to the MCP tool Python script
        tool_name (str): Name of the MCP tool to call (e.g., "get-forecast")
        input_data (dict): Input parameters for the tool
    
    Returns:
        dict: The tool's output data or error information
        
    Protocol:
        Sends JSON to tool's stdin: {"type": "tool-call", "tool": "tool-name", "input": {...}}
        Receives JSON from stdout: {"type": "tool-result", "output": {...}}
    """
    try:
        # Prepare MCP protocol message
        mcp_request = {
            "type": "tool-call",
            "tool": tool_name,
            "input": input_data
        }
          # Execute the MCP tool as a subprocess
        result = subprocess.run(
            ["python", tool_path],
            input=json.dumps(mcp_request),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            # Parse the JSON output from the MCP tool
            lines = result.stdout.strip().split('\n')
            for line in lines:
                try:
                    data = json.loads(line)
                    if data.get("type") == "tool-result":
                        return data["output"]
                except:
                    continue
            return {"error": "No valid tool result found"}
        else:
            return {"error": f"Tool execution failed: {result.stderr}"}
            
    except Exception as e:
        return {"error": str(e)}

@app.route("/weather", methods=["POST"])
def weather():
    """
    HTTP endpoint for weather forecast requests.
    
    Expected JSON payload: {"location": "city name"}
    Returns: {"location": "city", "forecast": "weather description"}
    """
    print(f"Weather request received: {request.get_json()}")
    data = request.get_json()
    location = data.get("location", "")
    
    if not location:
        return jsonify({"error": "Missing location"}), 400
      # Call the weather MCP tool
    result = call_mcp_tool("/app/weather-tool/tool.py", "get-forecast", {"location": location})
    print(f"Weather result: {result}")
    return jsonify(result)

@app.route("/time", methods=["POST"])  
def time():
    """
    HTTP endpoint for current time requests.
    
    Expected JSON payload: {"location": "city name"}
    Returns: {"location": "city", "time": "HH:MM:SS", "date": "YYYY-MM-DD", "timezone": "zone"}
    """
    print(f"Time request received: {request.get_json()}")
    data = request.get_json()
    location = data.get("location", "")
    
    if not location:
        return jsonify({"error": "Missing location"}), 400
      # Call the time MCP tool
    result = call_mcp_tool("/app/time-tool/tool.py", "get-time", {"location": location})
    print(f"Time result: {result}")
    return jsonify(result)

if __name__ == "__main__":
    # Run the Flask development server
    # host="0.0.0.0" allows access from outside the container
    # port=5000 matches the Docker port mapping
    # debug=True enables hot reloading and detailed error messages
    app.run(host="0.0.0.0", port=5000, debug=True)
