"""
AI Client — Azure AI Foundry (Anthropic) wrapper
Handles model selection, retries, token counting.
"""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def get_ai_client():
    """
    Return Anthropic client pointed at Azure AI Foundry.
    Falls back to direct Anthropic API, then None (triggers rule-based).
    """
    from config import get_settings
    settings = get_settings()

    endpoint = settings.azure_openai_chat_endpoint
    api_key = settings.azure_openai_api_key

    # Azure AI Foundry Anthropic path
    if endpoint and "services.ai.azure.com" in endpoint and api_key and "dummy" not in api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(
                base_url=endpoint.rstrip("/"),
                api_key=api_key,
                default_headers={"x-ms-useragent": "anthropic-azure/1.0"},
            )
            logger.info("AI client: Azure AI Foundry (Anthropic)")
            return client, settings.azure_openai_chat_deployment
        except Exception as e:
            logger.warning(f"Azure AI Foundry client failed: {e}")

    # Direct Anthropic API
    if settings.anthropic_api_key and settings.anthropic_api_key != "dummy-api-key":
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            logger.info("AI client: Direct Anthropic API")
            return client, settings.claude_model_default
        except Exception as e:
            logger.warning(f"Direct Anthropic client failed: {e}")

    logger.warning("AI client: None — rule-based fallback will be used")
    return None, None


def call_ai(
    messages: List[Dict],
    system: str,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> Optional[str]:
    """
    Call the AI model with messages + system prompt.
    Returns response text or None on failure.
    """
    client, default_model = get_ai_client()
    if not client:
        return None

    use_model = model or default_model
    try:
        response = client.messages.create(
            model=use_model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"AI call failed (model={use_model}): {e}")
        return None
