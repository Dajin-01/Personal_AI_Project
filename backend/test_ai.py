from unittest.mock import Mock, patch
import pytest

from ai import summarize_text

def test_summarize_text_handles_ai_responses():
    fake_response = Mock(
        status = "completed",
        output_text = "   테스트 요약     ",
    )

    with patch("ai.OpenAI") as mock_openai:
        fake_client = mock_openai.return_value.__enter__.return_value
        fake_client.responses.create.return_value = fake_response

        # 정상 응답: 앞뒤 공배를 제거해서 반환
        assert summarize_text("테스트 원문") == "테스트 요약"

        # 미완료 응답: 오류 발생
        fake_response.status = "incomplete"
        with pytest.raises(RuntimeError):
            summarize_text("테스트 원문")
        
        # 빈 응답: 오류 발생
        fake_response.status = "completed"
        fake_response.output_text = "    "
        with pytest.raises(RuntimeError):
            summarize_text("테스트 원문")