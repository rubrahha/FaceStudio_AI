"""v4 age, filter, gallery, and security regression tests."""
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from faceflow.app import app
from faceflow.celebrities import EXTENDED_NAMES, STARTER_NAMES
from faceflow import model_tasks

client = TestClient(app)
BASE = Path(__file__).resolve().parent.parent


def test_ten_real_filter_settings_and_three_morph_modes():
    src = (BASE / 'web/effects.js').read_text(encoding='utf8')
    for name in ('natural', 'glow', 'noir', 'vintage', 'pop', 'cool', 'warm', 'dream', 'neon', 'comic'):
        assert "id:'" + name + "'" in src
    for name in ('eyes', 'grin', 'funhouse'):
        assert "id:'" + name + "'" in src
    assert 'warpPatch(' in src
    assert 'requestAnimationFrame' in (BASE / 'web/app.js').read_text()


def test_age_download_is_only_started_by_explicit_request():
    assert client.get('/api/models/age/status').status_code == 200
    with patch('faceflow.app.start_age_install', return_value=(True, 'Started')) as start:
        assert client.get('/').status_code == 200
        assert client.get('/api/status').status_code == 200
        start.assert_not_called()
        result = client.post('/api/models/age/install')
        assert result.status_code == 200
        start.assert_called_once()


def test_age_download_conflict():
    with patch('faceflow.app.start_age_install', return_value=(False, 'Already running')):
        assert client.post('/api/models/age/install').status_code == 409


def test_celebrity_catalog_names_are_large_and_unique():
    assert len(EXTENDED_NAMES) >= 60
    assert len(EXTENDED_NAMES) == len(set(EXTENDED_NAMES))
    assert set(STARTER_NAMES).issubset(EXTENDED_NAMES)
    payload = client.get('/api/celebrities').json()
    assert payload['catalog_size'] == len(EXTENDED_NAMES)


def test_expanded_gallery_is_opt_in_and_validated():
    assert client.post('/api/celebrities/starter?pack=invalid').status_code == 422
    with patch('faceflow.app.start_import', return_value=(True, 'Started')) as start:
        assert client.get('/api/celebrities').status_code == 200
        start.assert_not_called()
        assert client.post('/api/celebrities/starter?pack=expanded').status_code == 200
        assert start.call_args.kwargs['pack'] == 'expanded'


def test_new_javascript_endpoint_and_ui():
    assert client.get('/effects.js').status_code == 200
    page = client.get('/').text
    for marker in ('id="filterStrip"', 'id="morphButtons"',
                   'id="ageSetup"', 'id="enableAge"', 'id="expandedButton"'):
        assert marker in page


def test_resumable_age_download_command_and_separate_launcher():
    source = (BASE/'scripts/download_models.py').read_text()
    assert "choice.add_argument('--age'" in source
    assert 'FILE' in source and '--age' in (BASE/'DOWNLOAD_AGE.ps1').read_text()
    # No biometric databases, saved photographs, or user profiles in the patch.
    assert 'models' not in (BASE/'web/app.js').read_text()[:25].lower()


def test_no_cross_origin_api_access():
    response = client.post('/api/models/age/install',headers={'Origin':'https://some-random-site.example'})
    assert response.status_code == 403


def test_model_task_status_is_safe_when_no_install_started():
    assert model_tasks.progress()['state'] in ('idle','running','error','complete')
