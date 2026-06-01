"""Tests for google-genai client construction."""

from unittest.mock import Mock

import pytest

from app.core.config import Settings
from app.llm.genai_client import build_genai_client


def test_build_genai_client_uses_ai_studio_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_factory = Mock(return_value=object())
    monkeypatch.setattr("app.llm.genai_client.genai.Client", client_factory)
    settings = Settings(GEMINI_USE_VERTEX=False, GEMINI_API_KEY="studio-key")

    build_genai_client(settings)

    client_factory.assert_called_once_with(api_key="studio-key")


def test_build_genai_client_uses_vertex_with_service_account_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_factory = Mock(return_value=object())
    credentials = object()
    credential_factory = Mock(return_value=credentials)
    monkeypatch.setattr("app.llm.genai_client.genai.Client", client_factory)
    monkeypatch.setattr(
        "google.oauth2.service_account.Credentials.from_service_account_info",
        credential_factory,
    )
    settings = Settings(
        GEMINI_USE_VERTEX=True,
        GOOGLE_CLOUD_PROJECT="gasbot-prod",
        GOOGLE_CLOUD_LOCATION="us-central1",
        GOOGLE_APPLICATION_CREDENTIALS_JSON='{"client_email": "svc@example.com"}',
    )

    build_genai_client(settings)

    credential_factory.assert_called_once_with(
        {"client_email": "svc@example.com"},
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    client_factory.assert_called_once_with(
        vertexai=True,
        project="gasbot-prod",
        location="us-central1",
        credentials=credentials,
    )


def test_build_genai_client_uses_vertex_adc_without_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_factory = Mock(return_value=object())
    monkeypatch.setattr("app.llm.genai_client.genai.Client", client_factory)
    settings = Settings(
        GEMINI_USE_VERTEX=True,
        GOOGLE_CLOUD_PROJECT="gasbot-prod",
        GOOGLE_CLOUD_LOCATION="asia-southeast1",
        GOOGLE_APPLICATION_CREDENTIALS_JSON=None,
    )

    build_genai_client(settings)

    client_factory.assert_called_once_with(
        vertexai=True,
        project="gasbot-prod",
        location="asia-southeast1",
        credentials=None,
    )
