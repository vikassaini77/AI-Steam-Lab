import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Set, Union
from fastapi import HTTPException, status
import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

STANDARD_ALLOWED_ALGORITHMS = {
    "HS256",
    "HS384",
    "HS512",
    "RS256",
    "RS384",
    "RS512",
    "ES256",
    "ES384",
    "ES512",
    "EdDSA",
}


class SupabaseJWTVerifier:
    """
    Enterprise-grade Supabase JWT Verifier with explicit claim enforcement and key rotation.

    Security Capabilities:
    1. Cryptographic signature verification supporting multi-secret rotation and JWKS.
    2. Explicit claim validation:
       - 'iss': Expected issuer (e.g. {SUPABASE_URL}/auth/v1).
       - 'aud': Expected audience (default: 'authenticated').
       - 'sub': Required, non-empty, valid user identifier.
       - 'exp': Strict expiration validation with configurable clock drift leeway.
       - 'iat': Issued-at timestamp validation (rejects tokens issued in future or after exp).
    3. Algorithm whitelist enforcement:
       - Configurable via SUPABASE_JWT_ALGORITHM / SUPABASE_JWT_ALGORITHMS.
       - Rejects 'none' algorithm and unapproved algorithms.
    4. Key rotation support:
       - Symmetric: Multiple secrets in rotation order or mapped by 'kid'.
       - Asymmetric: Dynamic public key resolution via Supabase Auth JWKS endpoint.
    """

    def __init__(
        self,
        secrets: Optional[Union[List[str], str]] = None,
        keys_by_kid: Optional[Dict[str, str]] = None,
        public_keys: Optional[Union[List[str], str]] = None,
        jwks_url: Optional[str] = None,
        allowed_algorithms: Optional[List[str]] = None,
        expected_issuer: Optional[str] = None,
        verify_issuer: bool = True,
        expected_audience: Union[str, List[str]] = "authenticated",
        verify_audience: bool = True,
        leeway: float = 10.0,
        jwks_cache_lifespan: float = 300.0,
    ) -> None:
        # 1. Parse symmetric secrets (supports list or comma-separated string)
        self.secrets: List[str] = []
        if isinstance(secrets, str):
            self.secrets = [s.strip() for s in secrets.split(",") if s.strip()]
        elif isinstance(secrets, (list, tuple, set)):
            self.secrets = [str(s).strip() for s in secrets if str(s).strip()]

        # 2. Key mapping by 'kid'
        self.keys_by_kid: Dict[str, str] = dict(keys_by_kid or {})

        # 3. Static public keys (PEM strings)
        self.public_keys: List[str] = []
        if isinstance(public_keys, str):
            self.public_keys = [public_keys.strip()]
        elif isinstance(public_keys, (list, tuple, set)):
            self.public_keys = [str(k).strip() for k in public_keys if str(k).strip()]

        # 4. JWKS Endpoint & PyJWKClient for asymmetric key rotation
        self.jwks_url: Optional[str] = jwks_url.strip() if jwks_url else None
        self.jwks_client: Optional[PyJWKClient] = None
        if self.jwks_url:
            try:
                self.jwks_client = PyJWKClient(
                    self.jwks_url,
                    cache_jwk_set=True,
                    lifespan=jwks_cache_lifespan,
                    timeout=10,
                )
            except Exception as e:
                logger.warning(f"Failed to initialize PyJWKClient for {self.jwks_url}: {e}")
                self.jwks_client = None

        # 5. Algorithm whitelist (strictly disallow 'none')
        raw_algorithms = allowed_algorithms or ["HS256"]
        cleaned_algs: List[str] = []
        for alg in raw_algorithms:
            cleaned = str(alg).strip().upper()
            if cleaned == "NONE":
                raise ValueError("Unsigned 'none' algorithm cannot be included in allowed algorithms.")
            if cleaned:
                cleaned_algs.append(cleaned)
        self.allowed_algorithms: List[str] = cleaned_algs or ["HS256"]

        # 6. Claim validation configuration
        self.expected_issuer: Optional[str] = expected_issuer.strip() if expected_issuer else None
        self.verify_issuer: bool = verify_issuer and bool(self.expected_issuer)
        self.expected_audience: Union[str, List[str]] = expected_audience
        self.verify_audience: bool = verify_audience
        self.leeway: float = max(0.0, float(leeway))

        # Required claims set
        self.required_claims: Set[str] = {"sub", "exp"}
        if self.verify_issuer:
            self.required_claims.add("iss")
        if self.verify_audience:
            self.required_claims.add("aud")

    @property
    def is_configured(self) -> bool:
        """Returns True if any local cryptographic verification key or JWKS is available."""
        return bool(
            self.secrets
            or self.keys_by_kid
            or self.public_keys
            or self.jwks_client
        )

    @classmethod
    def from_env(cls) -> "SupabaseJWTVerifier":
        """Instantiates a SupabaseJWTVerifier from active environment variables."""
        # 1. Symmetric secrets
        secrets_raw = os.getenv("SUPABASE_JWT_SECRET")
        secrets: List[str] = []
        if secrets_raw:
            secrets = [s.strip() for s in secrets_raw.split(",") if s.strip()]

        # 2. Key mapping by kid from JSON
        keys_by_kid: Dict[str, str] = {}
        jwt_keys_json = os.getenv("SUPABASE_JWT_KEYS")
        if jwt_keys_json:
            try:
                parsed = json.loads(jwt_keys_json)
                if isinstance(parsed, dict):
                    keys_by_kid.update(parsed)
                elif isinstance(parsed, list):
                    for k in parsed:
                        if isinstance(k, str) and k.strip() and k.strip() not in secrets:
                            secrets.append(k.strip())
            except Exception as e:
                logger.warning(f"Error parsing SUPABASE_JWT_KEYS JSON: {e}")
                for s in jwt_keys_json.split(","):
                    if s.strip() and s.strip() not in secrets:
                        secrets.append(s.strip())

        # 3. Public keys
        public_keys: List[str] = []
        pk_env = os.getenv("SUPABASE_JWT_PUBLIC_KEY") or os.getenv("SUPABASE_JWT_PUBLIC_KEYS")
        if pk_env:
            public_keys = [pk.strip() for pk in pk_env.split("---END PUBLIC KEY---") if pk.strip()]
            public_keys = [f"{pk}---END PUBLIC KEY---" if not pk.endswith("---END PUBLIC KEY---") else pk for pk in public_keys]

        # 4. Allowed algorithms
        algs_env = os.getenv("SUPABASE_JWT_ALGORITHMS") or os.getenv("SUPABASE_JWT_ALGORITHM")
        if algs_env:
            allowed_algs = [a.strip().upper() for a in algs_env.split(",") if a.strip()]
        else:
            allowed_algs = ["HS256"]

        # 5. Expected issuer
        supabase_url = os.getenv("SUPABASE_URL")
        expected_issuer = os.getenv("SUPABASE_JWT_ISSUER")
        if not expected_issuer and supabase_url and supabase_url.startswith("http"):
            expected_issuer = f"{supabase_url.rstrip('/')}/auth/v1"

        # 6. Verify issuer flag
        verify_issuer_env = os.getenv("SUPABASE_JWT_VERIFY_ISSUER")
        if verify_issuer_env is not None:
            verify_issuer = verify_issuer_env.strip().lower() not in ("false", "0", "no", "off")
        else:
            verify_issuer = bool(expected_issuer)

        # 7. Audience
        expected_audience = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
        verify_aud_env = os.getenv("SUPABASE_JWT_VERIFY_AUDIENCE")
        verify_audience = (
            verify_aud_env.strip().lower() not in ("false", "0", "no", "off")
            if verify_aud_env is not None
            else True
        )

        # 8. Leeway
        leeway_env = os.getenv("SUPABASE_JWT_LEEWAY")
        try:
            leeway = float(leeway_env) if leeway_env else 10.0
        except ValueError:
            leeway = 10.0

        # 9. JWKS URL
        jwks_url = os.getenv("SUPABASE_JWKS_URL")
        has_asymmetric = any(alg.startswith(("RS", "ES")) or alg == "EDDSA" for alg in allowed_algs)
        if not jwks_url and supabase_url and supabase_url.startswith("http") and has_asymmetric:
            jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

        return cls(
            secrets=secrets,
            keys_by_kid=keys_by_kid,
            public_keys=public_keys,
            jwks_url=jwks_url,
            allowed_algorithms=allowed_algs,
            expected_issuer=expected_issuer,
            verify_issuer=verify_issuer,
            expected_audience=expected_audience,
            verify_audience=verify_audience,
            leeway=leeway,
        )

    def _resolve_candidate_keys(self, alg: str, kid: Optional[str], token: str) -> List[Any]:
        """Resolves candidate cryptographic keys based on algorithm, kid, and rotation pool."""
        candidates: List[Any] = []

        # Asymmetric keys (RS256, ES256, etc.)
        if alg.startswith("RS") or alg.startswith("ES") or alg == "EDDSA":
            if self.jwks_client:
                try:
                    signing_key = self.jwks_client.get_signing_key_from_jwt(token)
                    if signing_key and signing_key.key:
                        candidates.append(signing_key.key)
                except Exception as e:
                    logger.debug(f"JWKS resolution for kid {kid} failed: {e}")

            if kid and kid in self.keys_by_kid:
                candidates.append(self.keys_by_kid[kid])

            for pk in self.public_keys:
                if pk not in candidates:
                    candidates.append(pk)

            return candidates

        # Symmetric keys (HS256, HS384, HS512)
        if alg.startswith("HS"):
            # Check key by kid first
            if kid and kid in self.keys_by_kid:
                candidates.append(self.keys_by_kid[kid])

            # Append all configured symmetric secrets in rotation priority order
            for sec in self.secrets:
                if sec not in candidates:
                    candidates.append(sec)

            return candidates

        return candidates

    def _validate_explicit_claims(self, payload: Dict[str, Any]) -> None:
        """Enforces invariant checks on subject, expiration, issued-at, issuer, and audience."""
        # 1. Subject (sub)
        sub = payload.get("sub")
        if sub is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing required subject (sub) claim",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not isinstance(sub, (str, int)) or not str(sub).strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token subject (sub) cannot be empty or whitespace",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 2. Expiration (exp)
        exp = payload.get("exp")
        if exp is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing required expiration (exp) claim",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not isinstance(exp, (int, float)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expiration (exp) claim must be numeric timestamp",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 3. Issued-at (iat)
        iat = payload.get("iat")
        if iat is not None:
            if not isinstance(iat, (int, float)):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token issued-at (iat) claim must be numeric timestamp",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            now = time.time()
            if iat > (now + self.leeway):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token issued in the future (iat exceeds current server time)",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if iat > exp:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token timeline: issued-at (iat) cannot be after expiration (exp)",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        # 4. Issuer (iss)
        if self.verify_issuer and self.expected_issuer:
            iss = payload.get("iss")
            if not iss:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token missing required issuer (iss) claim",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if str(iss).rstrip("/") != self.expected_issuer.rstrip("/"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token issuer: expected '{self.expected_issuer}', got '{iss}'",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        # 5. Audience (aud)
        if self.verify_audience:
            aud = payload.get("aud")
            if not aud:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token missing required audience (aud) claim",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            expected_list = (
                [self.expected_audience]
                if isinstance(self.expected_audience, str)
                else list(self.expected_audience)
            )
            actual_list = [aud] if isinstance(aud, str) else list(aud)
            if not any(a in expected_list for a in actual_list):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token audience: expected one of {expected_list}, got {actual_list}",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Cryptographically validates token signature, algorithm, claims, and returns authenticated user info.
        Raises HTTPException(401) on any failure.
        """
        if not token or not isinstance(token, str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Empty or missing Bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Step 1: Inspect unverified header for algorithm and kid
        try:
            header = jwt.get_unverified_header(token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: malformed JWT structure",
                headers={"WWW-Authenticate": "Bearer"},
            )

        alg = header.get("alg")
        if not alg or str(alg).strip().lower() == "none":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unsigned tokens ('none' algorithm) are strictly forbidden",
                headers={"WWW-Authenticate": "Bearer"},
            )

        alg_upper = str(alg).strip().upper()
        if alg_upper not in self.allowed_algorithms:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Disallowed token algorithm '{alg}'. Allowed algorithms: {self.allowed_algorithms}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        kid = header.get("kid")

        # Step 2: Resolve candidate keys for rotation support
        candidate_keys = self._resolve_candidate_keys(alg=alg_upper, kid=kid, token=token)
        if not candidate_keys:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No verification key available matching token configuration",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Step 3: Decode & verify signature against candidate keys
        decode_options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": True,
            "verify_aud": self.verify_audience,
            "verify_iss": self.verify_issuer,
            "require": list(self.required_claims),
        }

        decoded_payload: Optional[Dict[str, Any]] = None
        last_signature_error: Optional[Exception] = None

        for key in candidate_keys:
            try:
                decoded_payload = jwt.decode(
                    token,
                    key,
                    algorithms=[alg_upper],
                    audience=self.expected_audience if self.verify_audience else None,
                    issuer=self.expected_issuer if (self.verify_issuer and self.expected_issuer) else None,
                    leeway=self.leeway,
                    options=decode_options,
                )
                break
            except jwt.InvalidSignatureError as e:
                last_signature_error = e
                continue
            except jwt.ExpiredSignatureError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except jwt.ImmatureSignatureError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token issued in the future (invalid iat)",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except jwt.InvalidIssuerError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token issuer: expected '{self.expected_issuer}'",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except jwt.InvalidAudienceError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token audience: expected '{self.expected_audience}'",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except jwt.MissingRequiredClaimError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Token missing required claim: {str(e)}",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except jwt.InvalidAlgorithmError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid algorithm: {str(e)}",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except jwt.InvalidTokenError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token: {str(e)}",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        if decoded_payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token signature: verification failed against all configured keys",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Step 4: Strict explicit claim invariant validation
        self._validate_explicit_claims(decoded_payload)

        # Step 5: Return normalized authenticated user identity
        return {
            "id": str(decoded_payload.get("sub")),
            "email": decoded_payload.get("email"),
            "role": decoded_payload.get("role", "authenticated") or "authenticated",
            "metadata": decoded_payload.get("user_metadata", {}) or {},
            "claims": decoded_payload,
        }

