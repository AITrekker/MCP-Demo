FROM python:3.11-slim

WORKDIR /app

# Install dependencies including flask-cors
RUN pip install --no-cache-dir flask flask-cors requests

# Copy files from root context
COPY mcp-server/server.py /app/server.py
COPY weather-tool/ /app/weather-tool/
COPY time-tool/ /app/time-tool/

EXPOSE 5000

CMD ["python", "/app/server.py"]
