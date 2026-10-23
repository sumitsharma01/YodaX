"""Administrator-only evaluation API; anonymous research cookies grant no access."""
import hashlib
import hmac
import secrets
import time
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .storage import setting
from .core import connect
from .shadow_store import summary

router=APIRouter(prefix='/api/shadow',tags=['Private model evaluation'])
COOKIE='yodax_shadow_admin'


def key():
    value=setting('SHADOW_ADMIN_TOKEN')
    if len(value)<32:
        raise HTTPException(503,'Private evaluation access is not configured.')
    return value


def authenticated(request):
    secret=key()
    bearer=request.headers.get('authorization','')
    if bearer.startswith('Bearer ') and hmac.compare_digest(hashlib.sha256(bearer[7:].encode()).digest(),hashlib.sha256(secret.encode()).digest()):
        return True
    token=request.cookies.get(COOKIE,'')
    try:
        expiry,nonce,signature=token.split('.')
        body=expiry+'.'+nonce
        expected=hmac.new(secret.encode(),body.encode(),hashlib.sha256).hexdigest()
        return int(expiry)>time.time() and int(expiry)<=time.time()+8*3600+60 and len(nonce)==32 and hmac.compare_digest(expected,signature)
    except (ValueError,TypeError):
        return False


def origin_check(request):
    origin=request.headers.get('origin')
    expected=setting('PUBLIC_ORIGIN').rstrip('/') or str(request.base_url).rstrip('/')
    if origin and origin != expected:
        raise HTTPException(403,'Origin is not allowed.')


def response(value,status=200):
    return JSONResponse(value,status_code=status,headers={'Cache-Control':'no-store','X-Robots-Tag':'noindex'})


class Login(BaseModel):
    token: str = Field(min_length=1,max_length=512)


@router.post('/login')
def login(body:Login,request:Request):
    origin_check(request)
    if not hmac.compare_digest(hashlib.sha256(body.token.encode()).digest(),hashlib.sha256(key().encode()).digest()):
        raise HTTPException(401,'Incorrect administrator token.')
    expiry=str(int(time.time())+8*3600)
    value=expiry+'.'+secrets.token_hex(16)
    signature=hmac.new(key().encode(),value.encode(),hashlib.sha256).hexdigest()
    result=response({'authenticated':True})
    result.set_cookie(COOKIE,value+'.'+signature,max_age=8*3600,httponly=True,
        secure=setting('YODAX_STORAGE')=='postgres' or request.url.scheme=='https',samesite='strict',path='/api/shadow')
    return result


@router.post('/logout')
def logout(request:Request):
    origin_check(request)
    result=response({'authenticated':False});result.delete_cookie(COOKIE,path='/api/shadow')
    return result


@router.get('/session')
def session(request:Request):
    return response({'authenticated':authenticated(request)})


@router.get('')
def evaluation(request:Request):
    if not authenticated(request):
        raise HTTPException(401,'Administrator sign-in required.')
    try:
        with connect() as db:
            return response(summary(db))
    except Exception:
        raise HTTPException(503,'Evaluation storage is unavailable. Public forecasts are separate.') from None
