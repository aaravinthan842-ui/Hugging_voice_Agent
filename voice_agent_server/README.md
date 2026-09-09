# Voice Agent Server

## Tech Stack
- Python 3.11
- FastAPI
- Uvicorn
- uv
- Docker

## Run with Docker

docker build -t voice-agent-server .

docker run --env-file .env -p 8000:8000 voice-agent-server

## Health Check

GET /health

http://localhost:8000/health

## Port

8000

## Required Environment Variables

GEMINI_API_KEY=...