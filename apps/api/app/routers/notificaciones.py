from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

router = APIRouter()

@router.get("/")
async def list_notificaciones(db: AsyncSession = Depends(get_db)):
    return {"status": "not implemented", "resource": "notificaciones"}
