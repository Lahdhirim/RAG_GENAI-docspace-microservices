# Intelligent SharePoint

## Document Manager Service
```bash
uv run --package doc_manager_service .\services\doc_manager_service\database\tables.py
```

```bash
uv run --package doc-manager-service uvicorn app:app --app-dir services/doc_manager_service --reload --port 8000
```