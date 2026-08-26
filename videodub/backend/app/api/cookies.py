from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from app.core.downloader import (
    save_cookies, get_cookies_status, get_all_cookies_status,
    delete_cookies, SUPPORTED_PLATFORMS, validate_cookies_content
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class CookiesRequest(BaseModel):
    platform: str
    cookies: str


@router.post("/upload")
async def upload_cookies(req: CookiesRequest):
    logger.info(f"Upload cookies request: platform={req.platform}, cookies_length={len(req.cookies)}")
    
    if req.platform not in SUPPORTED_PLATFORMS:
        logger.error(f"Unsupported platform: {req.platform}")
        raise HTTPException(status_code=400, detail=f"Nền tảng không hỗ trợ: {req.platform}")

    # Validate cookies content before saving
    is_valid, message = validate_cookies_content(req.cookies, req.platform)
    logger.info(f"Validation result: is_valid={is_valid}, message={message}")
    
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    success = save_cookies(req.platform, req.cookies)
    logger.info(f"Save result: success={success}")
    
    if not success:
        raise HTTPException(status_code=500, detail="Không thể lưu cookies")
    return {"status": "ok", "message": f"Đã lưu cookies cho {SUPPORTED_PLATFORMS[req.platform]['name']}: {message}"}


@router.post("/upload-file/{platform}")
async def upload_cookies_file(platform: str, file: UploadFile = File(...)):
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Nền tảng không hỗ trợ: {platform}")
    content = await file.read()
    cookies_text = content.decode("utf-8")

    # Validate cookies content before saving
    is_valid, message = validate_cookies_content(cookies_text, platform)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    success = save_cookies(platform, cookies_text)
    if not success:
        raise HTTPException(status_code=500, detail="Không thể lưu cookies")
    return {"status": "ok", "message": f"Đã lưu cookies từ file cho {SUPPORTED_PLATFORMS[platform]['name']}: {message}"}


@router.get("/status")
async def all_cookies_status():
    return get_all_cookies_status()


@router.get("/status/{platform}")
async def cookies_status(platform: str):
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Nền tảng không hỗ trợ: {platform}")
    return get_cookies_status(platform)


@router.delete("/{platform}")
async def remove_cookies(platform: str):
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Nền tảng không hỗ trợ: {platform}")
    success = delete_cookies(platform)
    if not success:
        raise HTTPException(status_code=500, detail="Không thể xóa cookies")
    return {"status": "ok", "message": f"Đã xóa cookies cho {SUPPORTED_PLATFORMS[platform]['name']}"}


@router.get("/platforms")
async def list_platforms():
    return SUPPORTED_PLATFORMS


@router.post("/validate")
async def validate_cookies(req: CookiesRequest):
    """Validate cookies without saving"""
    if req.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Nền tảng không hỗ trợ: {req.platform}")
    is_valid, message = validate_cookies_content(req.cookies, req.platform)
    return {"valid": is_valid, "message": message}