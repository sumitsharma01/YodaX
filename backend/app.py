"""Small local API; inference runs separately via python -m backend.run."""
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .core import ROOT, connect
from .fx import cached
from .research import router as research_router, recover_interrupted

app = FastAPI(title='YodaX', version='0.2.0')
app.include_router(research_router)

@app.on_event('startup')
def recover_research():
    recover_interrupted()

@app.get('/api/health')
def health():
    with connect() as db:
        ready = db.execute('SELECT 1 FROM dashboard WHERE id=1').fetchone() is not None
    return {'status': 'ok', 'forecasts_ready': ready, 'inference': 'separate local Python job'}

@app.get('/api/dashboard')
def dashboard():
    with connect() as db:
        row = db.execute('SELECT payload FROM dashboard WHERE id=1').fetchone()
    if not row:
        raise HTTPException(503, 'No forecasts yet. Run .venv/bin/python -m backend.run')
    payload = json.loads(row['payload'])
    payload['fx'] = cached()
    return JSONResponse(payload, headers={'Cache-Control': 'no-store'})

@app.get('/api/evidence')
def evidence():
    from .evidence import build
    with connect() as db:
        row = db.execute('SELECT payload FROM dashboard WHERE id=1').fetchone()
        if not row:
            raise HTTPException(503, 'No saved forecasts available.')
        result = build(db, json.loads(row['payload']))
    return JSONResponse(result, headers={'Cache-Control': 'no-store'})

@app.get('/api/evidence/export')
def export_evidence():
    response = evidence()
    response.headers['Content-Disposition'] = 'attachment; filename="yodax-evidence.json"'
    return response

app.mount('/', StaticFiles(directory=ROOT / 'demo' / 'dist', html=True), name='website')
