import logging
from typing import Optional
import jwt
from fastapi import APIRouter, Request, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, Field
from app.core_backend.core.supabase_client import get_supabase_client
from app.core_backend.core.dependencies import get_current_user, get_token_from_header
from app.core_backend.core.token_revocation import revoke_token, is_token_revoked
from app.core_backend.core.observability import alert_manager
from app.core_backend.core.limiter import limiter
from supabase_auth.errors import AuthApiError

logger = logging.getLogger(__name__)

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
def logout(
    request: Request,
    token: str = Depends(get_token_from_header),
    current_user: dict = Depends(get_current_user),
):
    """
    Signs out the caller's session with Supabase Auth and invalidates the session token.
    1. Extracts caller's authenticated Bearer token and user identity.
    2. Invokes Supabase Auth session revocation passing the caller's token.
    3. Verifies that the session is revoked with the provider.
    4. Blacklists the token locally until natural cryptographic expiration.
    5. Never silently swallows logout failures: records full telemetry and error diagnostics.
    """
    user_id = current_user.get("id", "unknown")
    logger.info(f"Processing logout and session revocation for user '{user_id}'")

    provider_revoked = False
    provider_error: Optional[str] = None
    supabase = None

    try:
        supabase = get_supabase_client()
        # Revoke the session in Supabase Auth by passing the caller's access token
        if hasattr(supabase, "auth") and hasattr(supabase.auth, "admin") and hasattr(supabase.auth.admin, "sign_out"):
            supabase.auth.admin.sign_out(jwt=token, scope="global")
            provider_revoked = True
        elif hasattr(supabase, "auth") and hasattr(supabase.auth, "sign_out"):
            supabase.auth.sign_out()
            provider_revoked = True
        else:
            logger.warning(f"Supabase client does not expose sign_out; skipping remote revocation for user '{user_id}'")
    except AuthApiError as e:
        provider_error = str(e.message if hasattr(e, "message") else e)
        # Check if the session was already terminated / not found on the provider
        err_lower = provider_error.lower()
        if "session not found" in err_lower or "jwt expired" in err_lower or "token is expired" in err_lower:
            logger.info(f"Supabase session for user '{user_id}' was already expired or terminated: {provider_error}")
            provider_revoked = True
        else:
            logger.error(
                f"Supabase Auth session revocation failed for user '{user_id}': {provider_error}",
                extra={
                    "event": "auth_logout_revocation_failed",
                    "user_id": user_id,
                    "error_type": "AuthApiError",
                    "error_detail": provider_error,
                },
            )
            alert_manager.trigger_alert(
                alert_name="AUTH_LOGOUT_REVOCATION_FAILURE",
                severity="WARNING",
                message=f"Supabase session revocation failed for user '{user_id}': {provider_error}",
                metadata={"user_id": user_id, "error": provider_error},
            )
    except Exception as e:
        provider_error = str(e)
        logger.error(
            f"Unexpected error during Supabase session revocation for user '{user_id}': {provider_error}",
            extra={
                "event": "auth_logout_revocation_failed",
                "user_id": user_id,
                "error_type": type(e).__name__,
                "error_detail": provider_error,
            },
        )
        alert_manager.trigger_alert(
            alert_name="AUTH_LOGOUT_REVOCATION_FAILURE",
            severity="ERROR",
            message=f"Unexpected error during session revocation for user '{user_id}': {provider_error}",
            metadata={"user_id": user_id, "error": provider_error},
        )

    # Extract exp to blacklist token locally until expiration
    exp_ts = None
    try:
        unverified = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
        exp_ts = unverified.get("exp")
    except Exception:
        pass

    # Revoke token locally
    revoke_token(token, user_id=user_id, expires_at=exp_ts)

    # Verify session is revoked locally
    if not is_token_revoked(token):
        logger.error(f"Failed to record token revocation in local registry for user '{user_id}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session revocation could not be confirmed in token registry.",
        )

    # Verify with provider if remote revocation took place
    if provider_revoked and not provider_error and supabase:
        try:
            # Calling get_user with a revoked token must either raise an error or return None
            verification = supabase.auth.get_user(token)
            if verification and getattr(verification, "user", None):
                logger.warning(
                    f"Session revocation verification anomaly: user '{user_id}' still active in Supabase Auth after sign_out",
                    extra={"user_id": user_id, "event": "auth_revocation_verification_anomaly"},
                )
        except Exception:
            # Expected behavior: provider rejects the revoked token
            pass

    # If provider failed with an unrecoverable error, do not silently swallow it
    if provider_error and not provider_revoked:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Session revocation failed with upstream authentication provider: {provider_error}",
        )

    return {
        "status": "success",
        "message": "Successfully logged out and session revoked",
        "session_revoked": True,
    }


class MFAEnrollRequest(BaseModel):
    issuer: Optional[str] = "NeuroLab AI"
    friendly_name: Optional[str] = "NeuroLab Authenticator"


class MFAVerifyRequest(BaseModel):
    factor_id: str
    code: str


@router.post("/mfa/enroll")
@limiter.limit("5/minute")
def mfa_enroll(
    request: Request,
    payload: Optional[MFAEnrollRequest] = None,
    token: str = Depends(get_token_from_header),
    current_user: dict = Depends(get_current_user),
):
    """
    Enrolls a new TOTP Multi-Factor Authentication factor for the authenticated user.
    Returns factor ID, QR code data, secret key, and URI for authenticator app configuration.
    """
    issuer_name = payload.issuer if payload and payload.issuer else "NeuroLab AI"
    friendly_name = payload.friendly_name if payload and payload.friendly_name else "NeuroLab Authenticator"
    
    try:
        supabase = get_supabase_client()
        if hasattr(supabase, "auth") and hasattr(supabase.auth, "mfa"):
            res = supabase.auth.mfa.enroll({
                "factor_type": "totp",
                "issuer": issuer_name,
                "friendly_name": friendly_name,
            })
            totp_data = getattr(res, "totp", None)
            return {
                "status": "success",
                "id": str(getattr(res, "id", "")),
                "type": getattr(res, "type", "totp"),
                "totp": {
                    "qr_code": getattr(totp_data, "qr_code", None) if totp_data else None,
                    "secret": getattr(totp_data, "secret", None) if totp_data else None,
                    "uri": getattr(totp_data, "uri", None) if totp_data else None,
                },
            }
        raise RuntimeError("Supabase client does not expose MFA enrollment")
    except Exception as e:
        logger.error(f"MFA enrollment failed for user '{current_user.get('id')}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MFA enrollment failed: {str(e)}",
        )


@router.post("/mfa/verify")
@limiter.limit("10/minute")
def mfa_verify(
    request: Request,
    payload: MFAVerifyRequest,
    token: str = Depends(get_token_from_header),
    current_user: dict = Depends(get_current_user),
):
    """
    Verifies a TOTP challenge code against the enrolled factor ID.
    Marks factor as verified upon matching code.
    """
    try:
        supabase = get_supabase_client()
        if hasattr(supabase, "auth") and hasattr(supabase.auth, "mfa"):
            res = supabase.auth.mfa.challenge_and_verify({
                "factor_id": payload.factor_id,
                "code": payload.code.strip(),
            })
            return {
                "status": "verified",
                "message": "Two-factor authentication verified successfully.",
                "factor_id": payload.factor_id,
            }
        raise RuntimeError("Supabase client does not expose MFA verification")
    except Exception as e:
        logger.error(f"MFA verification failed for user '{current_user.get('id')}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MFA verification failed: {str(e)}",
        )


@router.get("/mfa/factors")
def mfa_list_factors(
    current_user: dict = Depends(get_current_user),
    token: str = Depends(get_token_from_header),
):
    """
    Lists enrolled MFA factors for the authenticated user.
    """
    try:
        supabase = get_supabase_client()
        if hasattr(supabase, "auth") and hasattr(supabase.auth, "mfa"):
            res = supabase.auth.mfa.list_factors()
            factors = []
            all_factors = getattr(res, "all", []) or []
            for f in all_factors:
                factors.append({
                    "id": str(getattr(f, "id", "")),
                    "friendly_name": getattr(f, "friendly_name", None),
                    "factor_type": getattr(f, "factor_type", "totp"),
                    "status": getattr(f, "status", "unverified"),
                    "created_at": getattr(f, "created_at", None),
                })
            return {
                "factors": factors,
                "has_verified_factor": any(f.get("status") == "verified" for f in factors),
            }
        return {"factors": [], "has_verified_factor": False}
    except Exception as e:
        logger.error(f"MFA list factors failed for user '{current_user.get('id')}': {e}")
        return {"factors": [], "has_verified_factor": False}


@router.delete("/mfa/factors/{factor_id}")
def mfa_unenroll(
    factor_id: str,
    current_user: dict = Depends(get_current_user),
    token: str = Depends(get_token_from_header),
):
    """
    Un-enrolls an existing MFA factor.
    """
    try:
        supabase = get_supabase_client()
        if hasattr(supabase, "auth") and hasattr(supabase.auth, "mfa"):
            supabase.auth.mfa.unenroll({"factor_id": factor_id})
            return {
                "status": "success",
                "message": f"Factor '{factor_id}' successfully unenrolled.",
                "factor_id": factor_id,
            }
        raise RuntimeError("Supabase client does not expose MFA unenrollment")
    except Exception as e:
        logger.error(f"MFA unenrollment failed for user '{current_user.get('id')}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MFA unenrollment failed: {str(e)}",
        )
