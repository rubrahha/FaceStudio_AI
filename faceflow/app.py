"""FaceStudio AI: local FastAPI web server. Never expose to a public network."""
from __future__ import annotations

import io
import os
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from PIL import Image, ImageOps, UnidentifiedImageError

from .engine import FaceEngine
from .storage import Gallery
from .celebrities import CelebrityGallery, EXTENDED_NAMES
from .starter_pack import start_import, get_progress
from .model_tasks import progress as age_progress, start_age_install

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'web'
MAX_UPLOAD = 8 * 1024 * 1024
MAX_PIXELS = 12_000_000
MAX_SIDE = 1600

app = FastAPI(title='FaceStudio AI', description='Local consent-based face image analysis', version='4.0.0', docs_url=None, redoc_url=None)
engine = FaceEngine()
gallery = Gallery()
celebs = CelebrityGallery()

@app.middleware('http')
async def security_headers(request: Request, call_next):
    # Browser frontend and webcam should only call our own local HTTP endpoint.
    origin = request.headers.get('origin')
    if origin and origin not in {'http://127.0.0.1:8765', 'http://localhost:8765'}:
        return JSONResponse({'detail': 'Cross-origin requests are not allowed.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data: blob:; connect-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'"
    return response


async def image_from_file(file: UploadFile) -> np.ndarray:
    if file.content_type not in ('image/jpeg', 'image/png', 'image/webp'):
        raise HTTPException(415, 'Upload a JPEG, PNG, or WebP photo.')
    content = await file.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(413, 'File too large. Maximum 8 MB.')
    if not content:
        raise HTTPException(400, 'Empty image.')
    try:
        with Image.open(io.BytesIO(content)) as src:
            if src.format not in ('JPEG', 'PNG', 'WEBP'):
                raise HTTPException(415, 'Unsupported or mismatched image format.')
            if src.width * src.height > MAX_PIXELS:
                raise HTTPException(413, 'Image too large. Maximum 12 megapixels.')
            image = ImageOps.exif_transpose(src).convert('RGB')
            image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            arr = np.array(image)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(400, f'Unable to decode image: {exc}') from exc


@app.get('/')
def home():
    return FileResponse(WEB / 'index.html')


@app.get('/app.css')
def css():
    return FileResponse(WEB / 'app.css', media_type='text/css')


@app.get('/effects.js')
def effects_js():
    return FileResponse(WEB / 'effects.js', media_type='application/javascript')


@app.get('/app.js')
def js():
    return FileResponse(WEB / 'app.js', media_type='application/javascript')


@app.get('/api/status')
def status():
    return {'engine': engine.status(), 'registered_people': len(gallery.list_people()), 'celebrity_references':len(celebs.list_refs()),
            'privacy': 'Photo analysis is in-memory. Enroll only with explicit consent.'}


@app.post('/api/analyze')
async def analyze(file: UploadFile = File(...), recognize: bool = Form(True),
                  estimate_age: bool = Form(True), estimate_appearance: bool = Form(False),
                  live: bool = Form(False), celebrity_mode: bool = Form(False)):
    img = await image_from_file(file)
    # Real-time requests use fewer expensive optional diagnostics; skip recognition
    # embeddings if there are no enrolled people. Offload blocking inference so
    # the HTTP server stays responsive to status/navigation while processing.
    match_enabled = recognize and engine.recognizer is not None and bool(gallery.list_people())
    celebrity_enabled = celebrity_mode and engine.recognizer is not None and bool(celebs.list_refs())
    result = await run_in_threadpool(engine.analyze, img, want_age=estimate_age,
                                    want_appearance=estimate_appearance, fast=live,
                                    want_features=(match_enabled or celebrity_enabled))
    for face in result['faces']:
        feature = face.pop('feature')
        face['identity'] = gallery.match(feature) if match_enabled and feature is not None else None
        face['celebrity_lookalikes'] = celebs.match(feature) if celebrity_enabled and feature is not None else []
    result['warnings'] = [
        'Age is a rough range, never a verified age.',
        'Appearance classification cannot determine a person’s gender identity.',
        'Photo aesthetics measure lighting and clarity, not beauty or human worth.',
        'Recognition matches are not suitable for access control or identification decisions.',
        'Celebrity suggestions are relative nearest matches from your gallery, just for fun.'
    ]
    return result


@app.post('/api/enroll')
async def enroll(file: UploadFile = File(...), name: str = Form(...), consent: bool = Form(False)):
    if consent is not True:
        raise HTTPException(400, 'Explicit permission from the person in the photo is required.')
    if engine.recognizer is None:
        raise HTTPException(503, 'SFace model is not installed. Run scripts/download_models.py --core.')
    img = await image_from_file(file)
    result = await run_in_threadpool(engine.analyze, img, want_age=False,
                                     want_appearance=False, want_features=True)
    if result['face_count'] != 1:
        raise HTTPException(422, 'Enrollment requires a photo with exactly one clearly visible face.')
    feature = result['faces'][0].pop('feature')
    if feature is None:
        raise HTTPException(422, 'Unable to obtain a face embedding. Try a clearer frontal photo.')
    try:
        person_id = gallery.enroll(name, feature)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {'ok': True, 'person_id': person_id, 'name': name.strip(), 'message': 'Sample stored locally. You can add up to eight photos per person.'}


@app.get('/api/people')
def people():
    return {'people': gallery.list_people()}


@app.delete('/api/people/{person_id}')
def remove_person(person_id: int):
    if person_id < 1 or not gallery.delete(person_id):
        raise HTTPException(404, 'Person not found.')
    return {'ok': True}


@app.delete('/api/people')
def clear_people(confirm: str = ''):
    if confirm != 'DELETE_ALL':
        raise HTTPException(400, 'Explicit confirmation required: confirm=DELETE_ALL')
    gallery.delete_all()
    return {'ok': True}


@app.get('/api/models/age/status')
def age_model_status():
    return {'installed': engine.age_net is not None, **age_progress()}


@app.post('/api/models/age/install')
def age_model_install():
    ok, message = start_age_install(engine)
    if not ok:
        raise HTTPException(409, message)
    return {'ok': True, 'message': message}


@app.post('/api/models/reload')
def reload_models():
    """Update the running local server after user has downloaded optional weights."""
    engine.load_models()
    return {'ok': True, 'engine':engine.status()}


@app.get('/api/celebrities')
def celebrity_list():
    return {'references':celebs.list_refs(), 'starter':get_progress(), 'catalog_size': len(EXTENDED_NAMES)}


@app.post('/api/celebrities')
async def add_celebrity(file: UploadFile = File(...), name: str = Form(...),
                        authorized: bool = Form(False)):
    if not authorized:
        raise HTTPException(400, 'Confirm you may use this reference photo.')
    if engine.recognizer is None:
        raise HTTPException(503, 'SFace recognition model is required; install core models.')
    img = await image_from_file(file)
    result = await run_in_threadpool(engine.analyze, img, want_age=False,
                                     want_appearance=False, fast=True, want_features=True)
    if result['face_count'] != 1 or result['faces'][0]['feature'] is None:
        raise HTTPException(422, 'Choose a clear portrait containing exactly one face.')
    try:
        celebs.add(name,result['faces'][0]['feature'])
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    return {'ok':True, 'name':name.strip()}


@app.delete('/api/celebrities/{ref_id}')
def delete_celebrity(ref_id: int):
    if ref_id < 1 or not celebs.delete(ref_id):
        raise HTTPException(404, 'Reference not found.')
    return {'ok':True}


@app.post('/api/celebrities/starter')
def import_starter_gallery(pack: str = 'starter'):
    if pack not in ('starter', 'expanded'):
        raise HTTPException(422, 'Invalid gallery pack.')
    ok,message = start_import(engine,celebs,pack=pack)
    if not ok:
        raise HTTPException(409,message)
    return {'ok':True, 'message':message}


def main():
    import uvicorn
    import webbrowser
    import threading
    print('FaceStudio AI at http://127.0.0.1:8765  (localhost only)')
    threading.Timer(2.0, lambda: webbrowser.open('http://127.0.0.1:8765')).start()
    uvicorn.run(app, host='127.0.0.1', port=8765, log_level='warning', access_log=False)


if __name__ == '__main__':
    main()
