"""
Generic MCP HTTP Bridge

This FastAPI server provides a RESTful API wrapper around any MCP-compliant tool.
It dynamically discovers the tool's capabilities and exposes appropriate endpoints.

Why this file is needed:
1. Separation of concerns: Keeps the MCP tool logic separate from HTTP API handling
2. Code reuse: One HTTP bridge can work with multiple different MCP tools
3. Automation: Automatically discovers and exposes all tools defined by an MCP server
4. Protocol translation: Bridges between HTTP requests and the MCP protocol format
5. Standardization: Provides consistent HTTP endpoints across different MCP tools

Usage:
    # Start the bridge for weather tool
    python run_bridge.py --server-path="./weather-server/server.py" --port=5001
    
    # Start the bridge for time tool
    python run_bridge.py --server-path="./time-server/server.py" --port=5002
"""

import subprocess
import sys
import json
import threading
import argparse
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, create_model
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional, Type, List
import inspect

def read_lines(pipe, buffer):
    """Continuously read lines from server stdout and append to buffer."""
    while True:
        line = pipe.readline()
        if not line:
            break
        buffer.append(line.strip())

def create_app(server_path: Optional[str] = None):
    """
    Factory function that creates a FastAPI app for a specific MCP tool server.
    
    Args:
        server_path: Path to the MCP tool server script
    
    Returns:
        FastAPI app configured for the specified tool
    """
    if not server_path:
        # Get the path from command line if not provided
        parser = argparse.ArgumentParser()
        parser.add_argument("--server-path", required=True, help="Path to MCP tool server")
        args, _ = parser.parse_known_args()
        server_path = args.server_path
    
    app = FastAPI()
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Start the MCP server to get tool descriptions
    server_proc = subprocess.Popen(
        ["python", server_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    # Read tool description
    stdout_buffer = []
    reader = threading.Thread(target=read_lines, args=(server_proc.stdout, stdout_buffer))
    reader.daemon = True
    reader.start()

    # Wait for the tool description
    while not stdout_buffer:
        pass

    first_line = stdout_buffer.pop(0)
    try:
        desc = json.loads(first_line)
        tools = desc.get("tools", [])
    except json.JSONDecodeError as e:
        server_proc.kill()
        raise RuntimeError(f"Invalid tool-description: {e}")
    
    server_proc.kill()  # We only needed the description
    
    # Create dynamic models for each tool
    for tool in tools:
        tool_name = tool["name"]
        input_schema = tool["input_schema"]
        output_schema = tool["output_schema"]
        
        # Create Pydantic model for request
        input_properties = {}
        for prop_name, prop_schema in input_schema.get("properties", {}).items():
            if prop_schema.get("type") == "string":
                input_properties[prop_name] = (str, ...)
        
        request_model = create_model(
            f"{tool_name.title().replace('-', '')}Request",
            **input_properties
        )
        
        # Create endpoint for this tool
        @app.post(f"/{tool_name}", response_model=None)
        async def tool_endpoint(request_data: request_model, tool=tool_name):
            # Convert Pydantic model to dict
            input_data = {k: v for k, v in request_data.dict().items()}
            
            # Start the MCP server subprocess
            server_proc = subprocess.Popen(
                ["python", server_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Read output
            stdout_buffer = []
            reader = threading.Thread(target=read_lines, args=(server_proc.stdout, stdout_buffer))
            reader.daemon = True
            reader.start()

            # Wait for tool description
            while not stdout_buffer:
                pass
            stdout_buffer.pop(0)  # Discard the tool description

            # Send tool call
            tool_call = {
                "type": "tool-call",
                "tool": tool,
                "input": input_data
            }
            server_proc.stdin.write(json.dumps(tool_call) + "\n")
            server_proc.stdin.flush()

            # Wait for result
            while not stdout_buffer:
                pass

            result_line = stdout_buffer.pop(0)
            try:
                result = json.loads(result_line)
            except json.JSONDecodeError:
                server_proc.kill()
                raise HTTPException(status_code=500, detail="Invalid response from tool")

            if result.get("type") != "tool-result" or "output" not in result:
                server_proc.kill()
                raise HTTPException(status_code=500, detail=f"Unexpected response: {result}")

            server_proc.kill()
            return result["output"]
    
    return app