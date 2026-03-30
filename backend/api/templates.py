from fastapi import APIRouter, Depends
from repository.supabase_client import get_templates
from core.auth import get_current_user

router = APIRouter()

@router.get("/templates")
async def list_templates(user_id: str = Depends(get_current_user)):
    return get_templates()
