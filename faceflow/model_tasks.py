"""Opt-in local age-model install with progress and no user-supplied URLs.

No network request happens on application startup. Only a user-clicked POST
starts downloading trusted, fixed model URLs onto the local computer.
"""
from __future__ import annotations

import threading
from pathlib import Path

from .engine import MODELS

_lock = threading.RLock()
_state = {'state': 'idle', 'message': 'Age model is optional.', 'downloaded_mb': 0.0}


def progress():
    with _lock:
        info = dict(_state)
    file = MODELS / 'age_net.caffemodel.part'
    if info['state'] == 'running' and file.exists():
        info['downloaded_mb'] = round(file.stat().st_size / 1048576, 1)
    return info


def start_age_install(engine):
    with _lock:
        if _state['state'] == 'running':
            return False, 'Download already running.'
        if engine.age_net is not None:
            _state.update(state='complete', message='Age model is already ready.', downloaded_mb=0)
            return True, 'Already installed.'
        _state.update(state='running', message='Downloading age estimator. Camera remains available.', downloaded_mb=0)

    def worker():
        try:
            # Import lazily so server launch never checks remote hosts.
            from scripts.download_models import FILES, download
            for filename, urls, minimum in FILES['extras'][:2]:
                with _lock:
                    _state['message'] = f'Downloading {filename} (can resume if interrupted)'
                if not download(filename, urls, minimum):
                    raise RuntimeError(f'{filename} unavailable. Try DOWNLOAD_AGE.ps1 later.')
            engine.load_models()
            if engine.age_net is None:
                raise RuntimeError('Age files downloaded but OpenCV could not load them.')
            with _lock:
                _state.update(state='complete', message='Age guessing is ready!', downloaded_mb=0)
        except Exception as exc:
            with _lock:
                _state.update(state='error', message=str(exc)[:180])

    threading.Thread(target=worker, name='age-model-setup', daemon=True).start()
    return True, 'Age download started.'
