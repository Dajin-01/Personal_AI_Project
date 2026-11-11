from ai import summarize_text

text = """
FastAPI로 프로젝트와 문서를 관리하는 API를 만들었습니다.
데이터는 PostgreSQL에 저장합니다.
프로젝트를 삭제하면 해당 프로젝트의 문서도 함께 삭제됩니다.
"""

print(summarize_text(text))