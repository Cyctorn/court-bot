FROM python:3.11-slim
# Set working directory
WORKDIR /app
# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*
# Copy requirements first for better caching
COPY requirements.txt .
# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
# Copy application code
COPY . .
# Create volume for persistent data
VOLUME ["/app/data"]
# Run the bot
CMD ["python", "courtbot.py"]
### `requirements.txt`
discord.py>=2.0.0
websockets>=11.0.0
aioconsole>=0.6.0
aiohttp>=3.8.0
websockets>=11.0.0