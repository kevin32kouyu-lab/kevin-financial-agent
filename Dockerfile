FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY requirements-dev.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN npm install && npm run build

ENV HOST=0.0.0.0
ENV PORT=8001

EXPOSE 8001

CMD ["python", "main.py"]
