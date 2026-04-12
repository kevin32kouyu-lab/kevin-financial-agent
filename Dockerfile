FROM python:3.13-slim

# Working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
COPY requirements-dev.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Install Node dependencies and build frontend
RUN npm install && npm run build

# Expose port
EXPOSE 8001

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
