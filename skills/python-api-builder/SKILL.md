# Skill: Python API Builder

## Purpose
Build high-performance, asynchronous REST APIs with FastAPI, Pydantic data schemas, SQLAlchemy ORM, and automated OpenAPI documentation.

## Inputs
- Resource specifications and entity models
- Database requirements
- Authentication and validation policies

## Process
1. Define Pydantic request and response schemas with strict type validation.
2. Define SQLAlchemy models with relationships and indexes.
3. Implement asynchronous CRUD service layer with dependency injection.
4. Wire FastAPI APIRouters with path operations and error handlers.
5. Generate integration tests using `TestClient` or `httpx.AsyncClient`.

## Outputs
- `app/schemas.py`
- `app/models.py`
- `app/routes.py`
- `tests/test_api.py`

## Validation
- Validate with `pytest` testing all CRUD endpoints, input validations (422 Unprocessable Entity), and error handling.
