import pytest
from fastapi.testclient import TestClient

from translai.app.main import app
from translai.app.config import Settings, settings
from translai.app.pipeline import translation_pipeline


def test_health_endpoint_returns_healthy():
    client = TestClient(app)
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'healthy'
    assert payload['version'] == '1.1.0'


def test_config_loading_without_provider_keys():
    cfg = Settings(text_provider_api_key='', image_provider_api_key='')
    assert cfg.text_provider_api_key == ''
    assert cfg.image_provider_api_key == ''


@pytest.mark.asyncio
async def test_language_detection_fallback(monkeypatch):
    def _raise(_):
        raise RuntimeError('forced failure')

    monkeypatch.setattr('translai.app.pipeline.detect', _raise)
    result = await translation_pipeline.detect_language('مرحبا بالعالم')
    assert result.language in {'ar', 'en'}
    assert result.confidence >= 0.0


def test_generate_requires_auth_when_missing_key():
    client = TestClient(app)
    response = client.post('/api/v1/generate', json={'prompt': 'hello', 'enhance': False})
    assert response.status_code == 401


def test_generate_forbidden_with_invalid_key():
    original_api_keys = settings.api_keys
    settings.api_keys = 'valid-key'
    client = TestClient(app)
    response = client.post(
        '/api/v1/generate',
        headers={'X-API-Key': 'invalid-key'},
        json={'prompt': 'hello', 'enhance': False},
    )
    settings.api_keys = original_api_keys
    assert response.status_code == 403


def test_generate_validates_prompt_length_with_valid_auth():
    original_api_keys = settings.api_keys
    original_max_prompt = settings.max_prompt_length
    settings.api_keys = 'valid-key'
    settings.max_prompt_length = 10

    client = TestClient(app)
    response = client.post(
        '/api/v1/generate',
        headers={'X-API-Key': 'valid-key'},
        json={'prompt': 'x' * 20, 'enhance': False},
    )

    settings.api_keys = original_api_keys
    settings.max_prompt_length = original_max_prompt

    assert response.status_code == 400
