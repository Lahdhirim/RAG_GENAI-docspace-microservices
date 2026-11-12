# Docspace: Document Management Platform
Docspace is a personal project I'm building to explore document processing, microservices, and container orchestration.

The idea is simple: upload and manage documents, automatically parse their content, and make the results available through a web interface. The backend is built with Python and FastAPI, while Docker and Kubernetes are used to manage the different services and scale the parsing workers.

## Document Manager Service (MySQL and APScheduler)
The Document Manager is responsible for keeping track of documents and their processing status.

It uses FastAPI to expose the API endpoints, MySQL to store document metadata and parsing jobs, and APScheduler to run background tasks.
The scheduler periodically scans the document directory, detects new or missing files, submits documents for parsing, and updates their status in the database.

Available at http://127.0.0.1:8000/

## SQL DB Service
MySQL stores information about documents and their parsing jobs, including processing status, execution times, errors, and extracted content.

### Optional : phpMyAdmin
For development and debugging, phpMyAdmin provides a simple way to inspect the database without writing SQL queries manually.

Available at http://localhost:8080/
<div style="text-align: center;">
    <img src="assets/phpAdmin.png" alt="CV" width="950", height="550"/>
</div>

## Parsing Service (Docling, OpenRouter and Redis Queue)

The Parsing Service handles the actual document processing.
It uses Docling to convert PDF documents into structured Markdown, with a vision-language model accessed through OpenRouter.
Parsing jobs are managed using Redis Queue (RQ), allowing the API to submit jobs without waiting for the parsing process to finish.

The service is split into two components:

- **Parsing API**: receives parsing requests, adds jobs to Redis, and exposes their status.
- **Parsing Workers**: consume jobs from the queue, process documents, and save the extracted Markdown content.

Since document parsing can be relatively expensive, the workers are designed to run as multiple replicas using Kubernetes.
This separation also keeps the API lightweight, while the heavier Docling dependencies are only installed in the workers.

## Frontend Application (Codex)
The frontend is an Angular and TypeScript application designed to provide a modern interface for document management.

This application is entirely developed by **OpenAI Codex**, allowing me to focus on the Python backend and infrastructure while leveraging AI-assisted development for the frontend.

Codex was given the following instructions:
- Build a modern and responsive Angular application.
- Integrate the existing FastAPI endpoints.
- Keep all frontend code strictly within the app/ directory.
- Do not modify the backend, Docker configuration, or other services.
- Submit all frontend changes through a dedicated GitHub Pull Request for review.

Available at http://localhost:4200/
<div style="text-align: center;">
    <img src="assets/web_app.png" alt="CV" width="950", height="550"/>
</div>

## Prerequisites
The project is designed to run locally with Docker Desktop.

Requirements are:
- Docker Desktop with Docker Compose.
- Kubernetes, enabled directly through Docker Desktop:

<div align="center">
  <img src="assets/k8s_docker.png" alt="Kubernetes configuration in Docker Desktop" width="950"/>
</div>

