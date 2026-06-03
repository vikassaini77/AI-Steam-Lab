from fastapi import Header, HTTPException
from typing import Optional
import os
import jwt

def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    Secure JWT token validation for Supabase.
    Extracts the Bearer token, decodes it using the SUPABASE_JWT_SECRET,
    and returns the decoded user payload.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token")
    
    token = authorization.split(" ")[1]
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    
    if not jwt_secret:
        print("WARNING: SUPABASE_JWT_SECRET is not set. Bypassing auth for development.")
        return {"sub": "default_user", "role": "authenticated"}
        
    try:
        # Supabase uses HS256 algorithm by default
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"], audience="authenticated")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")