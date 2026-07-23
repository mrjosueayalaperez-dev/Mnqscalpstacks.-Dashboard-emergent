"""Verified trading proof gallery — images stored in MongoDB (survive redeploys)."""
import base64
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8MB per shot
ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


def build_proof_router(db: Any, require_write_key: Any) -> APIRouter:
    router = APIRouter(prefix="/proof", tags=["public"])

    @router.get("/list")
    async def proof_list() -> Dict[str, Any]:
        """Public gallery metadata (images served separately by id)."""
        rows = (
            await db.proof_shots
            .find({}, {"_id": 0, "data": 0})
            .sort("uploaded_at", -1)
            .to_list(length=100)
        )
        for r in rows:
            r["url"] = f"/api/proof/image/{r['id']}"
        return {"shots": rows}

    @router.get("/image/{pid}")
    async def proof_image(pid: str) -> Response:
        doc = await db.proof_shots.find_one({"id": pid}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Proof shot not found")
        return Response(
            content=base64.b64decode(doc["data"]),
            media_type=doc["content_type"],
            headers={"Cache-Control": "public, max-age=86400"},
        )

    @router.post("/upload", dependencies=[Depends(require_write_key)], tags=["admin"])
    async def proof_upload(file: UploadFile = File(...), caption: str = Form("")) -> Dict[str, Any]:
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported type: {file.content_type}")
        raw = await file.read()
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="Image too large (max 8MB)")
        doc = {
            "id": str(uuid.uuid4()),
            "caption": caption.strip()[:200],
            "content_type": file.content_type,
            "size": len(raw),
            "data": base64.b64encode(raw).decode(),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.proof_shots.insert_one(dict(doc))
        return {"ok": True, "id": doc["id"], "url": f"/api/proof/image/{doc['id']}", "size": doc["size"]}

    @router.delete("/{pid}", dependencies=[Depends(require_write_key)], tags=["admin"])
    async def proof_delete(pid: str) -> Dict[str, Any]:
        result = await db.proof_shots.delete_one({"id": pid})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Proof shot not found")
        return {"ok": True, "deleted": pid}

    return router
