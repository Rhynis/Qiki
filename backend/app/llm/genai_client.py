"""Google GenAI client construction helpers."""

import json

from google import genai

from app.core.config import Settings

_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def build_genai_client(settings: Settings) -> genai.Client:
    """Build a google-genai client for AI Studio or Vertex AI."""
    if settings.GEMINI_USE_VERTEX:
        credentials = None
        if settings.GOOGLE_APPLICATION_CREDENTIALS_JSON:
            from google.oauth2 import service_account

            info = json.loads(settings.GOOGLE_APPLICATION_CREDENTIALS_JSON)
            credentials = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
                info,
                scopes=[_CLOUD_PLATFORM_SCOPE],
            )
        return genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION,
            credentials=credentials,
        )
    return genai.Client(api_key=settings.GEMINI_API_KEY)
