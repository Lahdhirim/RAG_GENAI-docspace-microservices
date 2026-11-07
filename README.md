# Intelligent SharePoint

## Document Manager Service

Available on http://127.0.0.1:8000/

## SQL DB Service

### Optional : phpMyAdmin

Available on http://localhost:8080/

## Frontend Application (Codex)
The frontend is an Angular and TypeScript application designed to provide a modern interface for document management.

This application is entirely developed by **OpenAI Codex**, allowing me to focus on the Python backend and infrastructure while leveraging AI-assisted development for the frontend.

Codex was given the following instructions:
- Build a modern and responsive Angular application.
- Integrate the existing FastAPI endpoints.
- Keep all frontend code strictly within the app/ directory.
- Do not modify the backend, Docker configuration, or other services.
- Submit all frontend changes through a dedicated GitHub Pull Request for review.

Available on http://localhost:4200/

## Prerequisites

Before running the application, ensure you have the following installed:
- Docker and Docker Compose
- Node.js and npm (for the frontend)
- Python 3.9+ (for the backend)