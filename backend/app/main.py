from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.services.events import DuplicateDeliveryConflict
from sqlalchemy import text
from app.api.routes import router
from app.config import settings
from app.db import engine
app = FastAPI(title='SprintGraph', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=[settings().frontend_origin], allow_methods=['GET', 'POST', 'PATCH'], allow_headers=['Authorization', 'Content-Type'])
app.include_router(router, prefix='/api')
@app.get('/health')
def health():
    return {'status': 'ok'}
@app.get('/ready')
def ready():
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        return {'status': 'ready'}
    except Exception:
        raise HTTPException(503, 'Database unavailable') from None


@app.exception_handler(DuplicateDeliveryConflict)
async def delivery_conflict(request, exc):
    return JSONResponse(status_code=409, content={'detail': 'Delivery ID already belongs to a different event'})
