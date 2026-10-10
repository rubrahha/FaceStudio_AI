"""Optional Wikimedia thumbnail import; only public reference photos travel over network.

Does NOT upload live frames or user photos. No reference images are stored; only
local feature embeddings. Thumbnails may be copyrighted: not bundled/distributed.
"""
from __future__ import annotations

import io
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse
import urllib.request
from urllib.parse import urlparse

import cv2
import numpy as np
from PIL import Image, ImageOps
from .celebrities import STARTER_NAMES, EXTENDED_NAMES

_lock = threading.Lock()
_progress = {'state': 'idle', 'done': 0, 'total':len(STARTER_NAMES), 'added':0,
             'message':'Not started'}

def get_progress():
    with _lock:
        return dict(_progress)

def _update(**items):
    with _lock:
        _progress.update(items)

def wikipedia_reference(name):
    params = urllib.parse.urlencode({'action':'query', 'format':'json', 'redirects':'1',
                                     'prop':'pageimages', 'titles':name, 'pithumbsize':'480'})
    url = 'https://en.wikipedia.org/w/api.php?' + params
    request = urllib.request.Request(url, headers={'User-Agent':'FaceStudioAI/3.0 (local demo; Wikimedia thumbnail credit)'})
    with urllib.request.urlopen(request, timeout=8) as response:
        raw = response.read(160_000)
    pages = json.loads(raw).get('query',{}).get('pages',{})
    thumb = next((item.get('thumbnail', {}).get('source') for item in pages.values() if item.get('thumbnail')), None)
    if not thumb:
        raise ValueError('No thumbnail')
    parsed = urlparse(thumb)
    if parsed.scheme != 'https' or parsed.hostname not in ('upload.wikimedia.org', 'commons.wikimedia.org'):
        raise ValueError('Unexpected thumbnail source')
    request = urllib.request.Request(thumb, headers={'User-Agent':'FaceStudioAI/3.0'})
    with urllib.request.urlopen(request, timeout=8) as response:
        if response.headers.get('Content-Length') and int(response.headers['Content-Length']) > 4*1024*1024:
            raise ValueError('Thumbnail too large')
        raw = response.read(4*1024*1024+1)
    if len(raw)>4*1024*1024: raise ValueError('Thumbnail too large')
    with Image.open(io.BytesIO(raw)) as picture:
        picture=ImageOps.exif_transpose(picture).convert('RGB')
        if picture.width*picture.height>2_000_000: picture.thumbnail((1200,1200))
        img=cv2.cvtColor(np.asarray(picture),cv2.COLOR_RGB2BGR)
    credit_url='https://en.wikipedia.org/wiki/'+urllib.parse.quote(name.replace(' ','_'))
    return img, credit_url

def import_starter(engine, celebrity_gallery, names=STARTER_NAMES):
    existing = {ref['name'].lower() for ref in celebrity_gallery.list_refs()}
    _update(state='running',done=0,total=len(names),added=0,
            message='Fetching reference portraits in parallel')

    def fetch_candidate(name):
        if name.lower() in existing:
            return name, None, None, 'cached'
        img,url = wikipedia_reference(name)
        return name,img,url,'fetched'

    done = added = 0
    # Bounded parallel *portrait downloads* keep the optional starter pack responsive.
    # Inference is still serialized through engine.lock for thread safety.
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix='celeb-portrait') as pool:
        jobs = {pool.submit(fetch_candidate, name):name for name in names}
        for task in as_completed(jobs):
            name=jobs[task]
            try:
                _, img, credit_url, mode = task.result()
                if mode!='cached':
                    result=engine.analyze(img, want_age=False, want_appearance=False,
                                          fast=True, want_features=True)
                    faces=result['faces']
                    if len(faces)!=1 or faces[0]['feature'] is None:
                        raise ValueError('No suitable single face')
                    celebrity_gallery.add(name, faces[0]['feature'], credit_url)
                    added+=1
                    message=f'Added {name}'
                else:
                    message=f'Already saved: {name}'
            except Exception:
                message=f'Skipped {name} (portrait unavailable)'
            done+=1
            _update(done=done,added=added,message=message)
    _update(state='complete',done=done,added=added,
            message=f'Added {added} reference faces. You can also add portraits manually.')

# Job is started explicitly by a user click, never on launch.
def start_import(engine, celebrity_gallery, pack='starter'):
    if engine.recognizer is None:
        return False, 'SFace recognition model is not installed.'
    with _lock:
        if _progress['state']=='running':
            return False, 'Import already in progress.'
        _progress.update(state='running', done=0, added=0, message='Preparing reference gallery')
    def runner():
        try: import_starter(engine, celebrity_gallery, EXTENDED_NAMES if pack == 'expanded' else STARTER_NAMES)
        except Exception as exc: _update(state='error',message=str(exc)[:150])
    threading.Thread(target=runner, daemon=True, name='facestudio-starter').start()
    return True, 'Starter gallery requested.'
