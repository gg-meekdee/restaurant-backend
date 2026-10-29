# Backend — FastAPI + PostgreSQL

## Layout
- app/api/routes/ — thin route handlers, one file per domain
- app/models/ — SQLAlchemy ORM models
- app/schemas/ — Pydantic request/response schemas
- app/services/ — business logic
- alembic/versions/ — migrations

## Patterns
- Routes: `async def` + `Depends(get_db)` for session
- Return Pydantic schemas, not ORM objects
- Errors: `HTTPException(status_code=..., detail=...)`
- After model changes: `alembic revision --autogenerate -m "msg"`, review the file, then `alembic upgrade head`

## Domain
Single-restaurant food ordering. Ghana. GHS currency. Cash + MoMo payment.
Rider types: permanent (has app access) and on_demand (counter assigns).
Delivery: zonal pricing, Haversine distance, quote endpoint at POST /api/delivery/quote