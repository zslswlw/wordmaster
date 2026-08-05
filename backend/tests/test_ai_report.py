import asyncio
from unittest.mock import AsyncMock

from app import models
from app.routers import ai as ai_router
from app.services.ai import AiService, InteractiveAiGenerationError
from app.services.ai.base import ProviderConfig
from app.services.ai.deepseek import DeepSeekProvider
from app.services.ai.minimax import MiniMaxProvider


VALID_ANALYSIS = {
    "patterns": [
        {
            "type": "double_letter_missing",
            "name": "双写辅音遗漏",
            "words": ["necessary"],
            "explanation": "把 necessary 分段检查，注意中间有两个 s。",
            "practice": ["immediate", "aggressive"],
        }
    ],
    "summary": "本轮重点检查双写辅音，输入后再按音节核对一次。",
}


def _service(api) -> tuple[AiService, object]:
    session = api["session"]()
    flags = models.FeatureFlags(
        id=1,
        error_analysis_enabled=True,
        story_enabled=True,
    )
    session.add(flags)
    session.commit()
    return AiService(session), session


def _minimax() -> MiniMaxProvider:
    return MiniMaxProvider(ProviderConfig(
        api_key="test",
        api_base="https://api.minimaxi.com",
        text_model="MiniMax-M3",
    ))


def _deepseek() -> DeepSeekProvider:
    return DeepSeekProvider(ProviderConfig(
        api_key="test",
        api_base="https://api.deepseek.com",
        text_model="deepseek-chat",
    ))


def test_error_analysis_repairs_invalid_json_once(api):
    service, session = _service(api)
    minimax = _minimax()
    minimax.chat_json = AsyncMock(side_effect=[
        RuntimeError("empty response"),
        VALID_ANALYSIS,
    ])
    service._minimax = minimax

    result = asyncio.run(service.analyze_errors([{
        "word": "necessary",
        "correct": "necessary",
        "user": "necesary",
        "meaning": "必要的",
    }]))

    assert result["status"] == "ready"
    assert result["provider"] == "minimax"
    assert result["patterns"][0]["words"] == ["necessary"]
    assert minimax.chat_json.await_count == 2
    assert minimax.chat_json.await_args_list[0].kwargs["thinking"] == {"type": "disabled"}
    assert minimax.chat_json.await_args_list[0].kwargs["queue_timeout"] == 15
    session.close()


def test_error_analysis_falls_back_when_minimax_keeps_hallucinating(api):
    service, session = _service(api)
    invalid = {
        **VALID_ANALYSIS,
        "patterns": [{**VALID_ANALYSIS["patterns"][0], "words": ["invented"]}],
    }
    minimax = _minimax()
    minimax.chat_json = AsyncMock(side_effect=[invalid, invalid])
    deepseek = _deepseek()
    deepseek.chat_json = AsyncMock(return_value=VALID_ANALYSIS)
    service._minimax = minimax
    service._deepseek = deepseek

    result = asyncio.run(service.analyze_errors([{
        "word": "necessary",
        "correct": "necessary",
        "user": "necesary",
        "meaning": "必要的",
    }]))

    assert result["provider"] == "deepseek"
    assert minimax.chat_json.await_count == 2
    assert deepseek.chat_json.await_count == 1
    session.close()


def test_story_repairs_draft_that_omits_a_target_word(api):
    service, session = _service(api)
    minimax = _minimax()
    invalid_story = (
        "At dawn, Mina reached the harbor with a fragile compass. She followed its needle "
        "through the market, met a sleepy baker, and traded her red umbrella for a map. "
        "By sunset, everyone laughed because the map led back to the same bakery door."
    )
    valid_story = (
        "At dawn, Mina reached the harbor with a fragile compass and a plan to rescue her "
        "sleepy uncle. She followed its needle through the market, traded a red umbrella "
        "for a map, and opened a tiny boat. By sunset, she discovered her uncle serving "
        "cakes beside the very dock where her journey began."
    )
    minimax.chat = AsyncMock(side_effect=[invalid_story, valid_story])
    service._minimax = minimax

    result = asyncio.run(service.generate_story(["harbor", "fragile", "rescue"]))

    assert result == valid_story
    assert minimax.chat.await_count == 2
    second_prompt = minimax.chat.await_args_list[1].args[0][-1]["content"]
    assert "missing target words: rescue" in second_prompt
    session.close()


def test_analysis_api_returns_safe_error_instead_of_raw_provider_text(api, monkeypatch):
    class FailingService:
        def __init__(self, _db):
            pass

        async def analyze_errors(self, _errors):
            raise InteractiveAiGenerationError(
                "invalid_ai_output",
                "AI 返回的分析格式异常，请稍后重试",
            )

    monkeypatch.setattr(ai_router, "AiService", FailingService)
    response = api["client"].post(
        "/api/ai/analyze-errors",
        headers=api["headers"],
        json={
            "errors": [{
                "word": "necessary",
                "correct": "necessary",
                "user": "necesary",
                "meaning": "必要的",
            }]
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "invalid_ai_output",
        "message": "AI 返回的分析格式异常，请稍后重试",
    }
    assert "JSON decode" not in response.text


def test_story_api_requires_three_different_words(api):
    response = api["client"].post(
        "/api/ai/story",
        headers=api["headers"],
        json={"words": ["harbor", "harbor", "fragile"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "请至少提供 3 个不同的错词"
