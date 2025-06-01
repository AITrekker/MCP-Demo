"""
Runner script for MCP HTTP Bridge

This script launches the FastAPI server for the specified MCP tool.

Usage:
    python run_bridge.py --server-path="./weather-server/server.py" --port=5001
    python run_bridge.py --server-path="./time-server/server.py" --port=5002
"""

import argparse
import uvicorn
from mcp_http_bridge import create_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run MCP HTTP Bridge")
    parser.add_argument("--server-path", required=True, help="Path to MCP tool server")
    parser.add_argument("--port", type=int, default=5001, help="Port to run the server on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the server to")
    
    args = parser.parse_args()
    
    # Create the app with the specified server path
    app = create_app(args.server_path)
    
    # Run the server
    uvicorn.run(app, host=args.host, port=args.port)