FROM python:3.11-slim

WORKDIR /app

# Install dependencies including flask-cors
RUN pip install --no-cache-dir flask flask-cors requests

# Copy files from root context
COPY bridge/bridge.py /app/bridge.py
COPY weather-server/ /app/weather-server/
COPY time-server/ /app/time-server/

EXPOSE 5000

CMD ["python", "/app/bridge.py"]
