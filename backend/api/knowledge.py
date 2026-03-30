from fastapi import APIRouter, HTTPException, Depends
from typing import List
from schema.extra_schema import KnowledgeCreate, KnowledgeUpdate
from repository.supabase_client import get_knowledge_items, insert_knowledge_item, delete_knowledge_item, update_knowledge_item
from utils.file_parser import parse_base64_file_to_text
from core.auth import get_current_user

router = APIRouter()

@router.get("/knowledge")
async def list_knowledge(user_id: str = Depends(get_current_user)):
    return get_knowledge_items(user_id)

@router.post("/knowledge/upload")
async def upload_knowledge(request: KnowledgeCreate, user_id: str = Depends(get_current_user)):
    # 如果 content 是 Base64 编码（通常前端上传 binary 时会这么做），则进行转换
    # 这里的逻辑满足用户“均转化成 .txt 格式”的要求
    parsed_content = request.content
    if request.content and len(request.content) > 100: # 简单判断是否可能含有编码
        # 尝试作为 base64 解析，如果失败则保留原样
        parsed_content = parse_base64_file_to_text(request.content, request.type)

    res = insert_knowledge_item(
        user_id=user_id,
        name=request.name.replace(".pdf", ".txt").replace(".docx", ".txt"), # 修改后缀名直观显示转换结果
        item_type="txt", # 统一类型为 txt
        size=request.size,
        tags=request.tags,
        content=parsed_content
    )
    return {"status": "success", "data": res}

@router.delete("/knowledge/{item_id}")
async def delete_knowledge(item_id: str, user_id: str = Depends(get_current_user)):
    res = delete_knowledge_item(item_id, user_id)
    if not res:
        raise HTTPException(status_code=404, detail="资料不存在或无权删除")
    return {"status": "success", "message": "资料已从您的账号中永久移除"}

@router.put("/knowledge/{item_id}")
async def update_knowledge(
    item_id: str,
    request: KnowledgeUpdate,
    user_id: str = Depends(get_current_user),
):
    res = update_knowledge_item(
        item_id=item_id,
        user_id=user_id,
        name=request.name,
        item_type=request.type,
        size=request.size,
        tags=request.tags,
        content=request.content,
    )
    if not res:
        raise HTTPException(status_code=404, detail="资料不存在或无权编辑")
    return {"status": "success", "data": res}
