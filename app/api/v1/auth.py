from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db_session
from app.models.identity import User
from app.schemas.auth import AuthResponse, LoginRequest, SignupRequest, UserResponse
from app.services.auth import clear_auth_cookies, login, refresh_user, set_auth_cookies, signup

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup_user(payload: SignupRequest, response: Response, db: AsyncSession = Depends(get_db_session)) -> AuthResponse:
    try:
        user = await signup(db=db, email=str(payload.email), password=payload.password, display_name=payload.display_name, organization_name=payload.organization_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    set_auth_cookies(response, str(user.id))
    return AuthResponse(user=UserResponse.model_validate(user))

@router.post("/login", response_model=AuthResponse)
async def login_user(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db_session)) -> AuthResponse:
    user = await login(db=db, email=str(payload.email), password=payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    set_auth_cookies(response, str(user.id))
    return AuthResponse(user=UserResponse.model_validate(user))

@router.post("/refresh", response_model=AuthResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db_session)) -> AuthResponse:
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token required")
    user = await refresh_user(db=db, token=token)
    if not user:
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    set_auth_cookies(response, str(user.id))
    return AuthResponse(user=UserResponse.model_validate(user))

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    clear_auth_cookies(response)

@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)
