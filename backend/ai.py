from openai import OpenAI

def summarize_text(content:str) -> str:
    with OpenAI() as client:
        response = client.responses.create(
            model = "gpt-6-luna",
            reasoning = {"effort":"none"},
            instructions = "입력된 글의 핵심을 한국어 두 문장으로 요약하세요.",
            input = content,
            max_output_tokens = 300,
            store = False,
        )
    
    summary = response.output_text.strip()

    if response.status != "completed" or not summary:
        raise RuntimeError("요약이 완료되지 않았습니다.")
    return summary