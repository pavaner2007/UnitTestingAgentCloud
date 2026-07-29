# AutoQA Agent API Documentation

## Base URL

```text
http://localhost:8000
```

## GET /health

Checks API health.

### Response

```json
{
  "status": "healthy",
  "service": "AutoQA Agent"
}
```

## POST /analyze-repository

Clones and analyzes a GitHub repository.

### Request Body

```json
{
  "github_url": "https://github.com/owner/repository"
}
```

### Success Response

```json
{
  "analysis_id": "uuid",
  "status": "completed",
  "report": {
    "analysis_id": "uuid",
    "repository_name": "repository",
    "repository_url": "https://github.com/owner/repository",
    "metadata": {},
    "technology_stack": {},
    "project_structure_summary": {},
    "number_of_files": 0,
    "number_of_apis_discovered": 0,
    "api_inventory": []
  }
}
```

### Error Responses

Invalid URL or clone failure:

```json
{
  "detail": "Invalid GitHub repository URL. Use https://github.com/owner/repo"
}
```

## GET /analysis/{id}

Returns a stored analysis report by ID.

### Response

```json
{
  "analysis_id": "uuid",
  "repository_name": "repository",
  "technology_stack": {},
  "api_inventory": []
}
```
