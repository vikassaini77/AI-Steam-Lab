from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, Field
from app.core_backend.core.supabase_client import get_supabase_client
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.core.limiter import limiter
from supabase_auth.errors import AuthApiError

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters long")
    name: Optional[str] = "Student"


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, req: LoginRequest):
    """
    Authenticates user credentials through Supabase Auth.
    Returns real JWT access and refresh tokens.
    Rejects invalid credentials with 401 Unauthorized.
    """
    try:
        supabase = get_supabase_client()
        res = supabase.auth.sign_in_with_password({
            "email": req.email,
            "password": req.password,
        })
        
        session = res.session
        user = res.user
        
        if not session or not session.access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed: Unable to obtain session from provider.",
            )
            
        user_metadata = getattr(user, "user_metadata", {}) or {}
        display_name = user_metadata.get("full_name") or user_metadata.get("name") or "Student"
        
        return {
            "token": session.access_token,
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "token_type": getattr(session, "token_type", "bearer") or "bearer",
            "expires_in": session.expires_in,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": display_name,
            },
        }
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {e.message}",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )


@router.post("/register")
@limiter.limit("5/minute")
def register(request: Request, req: RegisterRequest):
    """
    Registers a new user account with Supabase Auth.
    Enforces real credential creation and email verification.
    Rejects duplicate accounts and weak passwords with 400 Bad Request.
    """
    try:
        supabase = get_supabase_client()
        signup_payload = {
            "email": req.email,
            "password": req.password,
        }
        if req.name:
            signup_payload["options"] = {
                "data": {
                    "full_name": req.name,
                    "name": req.name,
                }
            }
            
        res = supabase.auth.sign_up(signup_payload)
        user = res.user
        session = res.session

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed: Provider did not return user details.",
            )

        return {
            "status": "registered",
            "message": "User registered successfully. Please verify your email if confirmation is enabled.",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": req.name,
            },
            "session": {
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
                "token_type": getattr(session, "token_type", "bearer") or "bearer",
                "expires_in": session.expires_in,
            } if session else None,
        }
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {e.message}",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration error: {str(e)}",
        )


@router.get("/me")
def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """
    Returns the authenticated user's profile.
    Requires a valid, non-expired Bearer access token.
    """
    return {"user": current_user}


@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user)):
    """
    Signs out the current session with Supabase Auth.
    Requires a valid, non-expired Bearer access token.
    """
    try:
        supabase = get_supabase_client()
        supabase.auth.sign_out()
    except Exception:
        pass
    return {"status": "success", "message": "Successfully logged out"}
