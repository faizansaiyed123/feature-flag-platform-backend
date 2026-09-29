from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Application liveness check")
async def health() -> dict[str, str]:
    return {"status": "ok"}
