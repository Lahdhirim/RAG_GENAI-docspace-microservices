# Intelligent SharePoint

## Document Manager Service
```bash
uv run --package doc_manager_service .\services\doc_manager_service\database\tables.py
```

```bash
uv run --package doc_manager_service uvicorn app:app --app-dir services/doc_manager_service --reload --port 8000
```

Available on http://127.0.0.1:8000/

## SQL DB Service

### Optional : phpMyAdmin

Available on http://localhost:8080/
