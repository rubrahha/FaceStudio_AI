"""Celebrity entertainment mode, safe APIs and non-blocking installation regressions."""
import io
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from faceflow.app import app
from faceflow.celebrities import CelebrityGallery
from faceflow import starter_pack

client = TestClient(app)

def photo():
    b=io.BytesIO()
    Image.new('RGB',(160,160),(128,135,140)).save(b,'JPEG')
    return b.getvalue()

def test_gallery_ranks_relative_matches_and_removes():
    with tempfile.TemporaryDirectory() as t:
        db=CelebrityGallery(Path(t)/'refs.db')
        a=np.zeros(128,dtype=np.float32);a[0]=1
        b=np.zeros(128,dtype=np.float32);b[1]=1
        db.add('Person A',a)
        db.add('Person B',b)
        refs=db.list_refs()
        assert len(refs)==2
        top=db.match(a)
        assert top[0]['name']=='Person A'
        assert top[0]['similarity']>0.9
        assert len(db.match(None))==0
        assert db.delete(refs[0]['id'])
        assert len(db.list_refs())==1

def test_gallery_rejects_invalid_vectors():
    with tempfile.TemporaryDirectory() as t:
        db=CelebrityGallery(Path(t)/'refs.db')
        try: db.add('Something', np.full(128,float('nan')))
        except ValueError: pass
        else: assert False,'invalid vectors must be rejected'

def test_no_raw_face_embedding_in_api_response():
    feature=[1.0]+[0.0]*127
    mock_result={'width':160,'height':160,'face_count':1,'faces':[{'index':1,'bbox':[3,4,110,110],
        'photo_aesthetics_score':85,'framing_score':91,'capture_tips':[],
        'brightness':120,'sharpness':90,'contrast':30,'head_tilt_degrees':None,
        'eyes_visible_estimate':None,'smile_pattern_detected':None,'age_estimate':None,
        'appearance_estimate':None,'landmarks':[],'feature':feature}]}
    with patch('faceflow.app.engine.analyze', return_value=mock_result),\
         patch('faceflow.app.celebs.list_refs', return_value=[{'id':1,'name':'Public Person'}]),\
         patch('faceflow.app.celebs.match',return_value=[{'name':'Public Person','similarity':.55,'credit_url':''}]),\
         patch('faceflow.app.engine.recognizer',object()):
        r=client.post('/api/analyze',data={'celebrity_mode':'true','recognize':'false','estimate_age':'false'},
                      files={'file':('pic.jpg',photo(),'image/jpeg')})
        assert r.status_code==200
        assert r.json()['faces'][0]['celebrity_lookalikes'][0]['name']=='Public Person'
        assert 'feature' not in r.text
        assert 'embedding' not in r.text

def test_starter_import_does_not_start_when_model_missing():
    with patch('faceflow.app.engine.recognizer',None):
        r=client.post('/api/celebrities/starter')
        assert r.status_code==409

def test_celeb_upload_requires_rights():
    r=client.post('/api/celebrities',data={'name':'Example Person','authorized':'false'},
                  files={'file':('pic.jpg',photo(),'image/jpeg')})
    assert r.status_code==400

def test_models_reload_endpoint():
    with patch('faceflow.app.engine.load_models') as call:
        r=client.post('/api/models/reload')
        assert r.status_code==200
        call.assert_called_once()

def test_quick_install_skips_optional_model_download():
    text=(Path(__file__).resolve().parent.parent/'INSTALL.ps1').read_text()
    assert 'if ($Extras)' in text
    assert 'scripts\\download_models.py --extras' in text
    assert 'DOWNLOAD_EXTRAS.ps1' in (Path(__file__).resolve().parent.parent/'web/app.js').read_text()

def test_frontend_v3_controls_present():
    html=client.get('/').text
    for s in ('data-mode="celebrity"','data-mode="party"','data-mode="vision"',
              'id="celebrityForm"','id="starterButton"','id="saveSelfie"','id="reloadModels"'):
        assert s in html
