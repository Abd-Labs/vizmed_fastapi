from fastapi import APIRouter,Depends
from app.core.security import api_key_authentication


router = APIRouter()

@router.get("/health-check", dependencies=[Depends(api_key_authentication)])
async def health_check():
    return {"status": "healthy"}
