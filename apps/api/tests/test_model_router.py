"""Model router billing / fail-fast behavior."""
from core.model_router import _is_billing_error, models_for_profile
from core.config import settings


def test_billing_error_402_message():
    assert _is_billing_error(
        Exception(
            "Error code: 402 - {'error': {'message': 'requires more credits'}}"
        )
    )


def test_billing_error_status_code():
    exc = Exception("payment required")
    exc.status_code = 402  # type: ignore[attr-defined]
    assert _is_billing_error(exc)


def test_non_billing_error():
    assert not _is_billing_error(Exception("Error code: 500 - internal server error"))
    assert not _is_billing_error(Exception("timeout connecting to provider"))


def test_background_profile_uses_cron_model_only():
    chain = models_for_profile("digest")
    assert chain == [settings.openrouter_cron_model or "openrouter/free"]


def test_interactive_profile_has_fallback_chain():
    chain = models_for_profile("agent_chat")
    assert len(chain) >= 2
    assert chain[-1] == (settings.openrouter_fallback_model or "openrouter/free")
