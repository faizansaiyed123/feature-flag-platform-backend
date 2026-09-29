from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.feature_flags import router as feature_flags_router
from app.api.v1.health import router as health_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.overview import router as overview_router
from app.api.v1.projects import router as projects_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(organizations_router)
api_router.include_router(projects_router)
api_router.include_router(feature_flags_router)
api_router.include_router(overview_router)
