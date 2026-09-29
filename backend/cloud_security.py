"""Signed anonymous browser sessions for private research conversations."""
import hashlib
import hmac
import secrets
from fastapi.responses import JSONResponse
from .storage import setting

async def session_middleware(request, call_next):
    if setting('YODAX_STORAGE') != 'postgres':
        return await call_next(request)
    secret = setting('SESSION_SECRET')
    if len(secret) < 32:
        return JSONResponse({'detail':'Cloud session configuration missing.'}, status_code=503)
    def signature(value):
        return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()
    token = request.cookies.get('yodax_session', '')
    owner, _, signed = token.partition('.')
    valid = len(owner) == 64 and hmac.compare_digest(signature(owner), signed)
    if not valid:
        owner = secrets.token_hex(32)
    request.state.owner = owner
    response = await call_next(request)
    if not valid:
        response.set_cookie('yodax_session', owner+'.'+signature(owner),
            max_age=60*60*24*30, httponly=True, secure=True, samesite='strict')
    return response
