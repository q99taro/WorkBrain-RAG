import os
import json
from datetime import datetime
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional, List

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class IntentAnalysis(BaseModel):
    intent: str = Field(description="Must be 'log' for recording work, or 'query' for asking questions about past work.")
    clean_contents: List[str] = Field(description="If log, the core content of the user's message, removing time adverbs.")
    clean_content: str = Field(description="If query, the exact question the user is asking, removing time adverbs.", default="")
    event_time: Optional[str] = Field(description="If intent is 'log', extract the specific ISO 8601 time. Return null if not specified.")
    query_start_time: Optional[str] = Field(description="If intent is 'query', extract the start of the requested time range in ISO 8601 format.")
    query_end_time: Optional[str] = Field(description="If intent is 'query', extract the end of the requested time range in ISO 8601 format.")

def analyze_intent(user_input: str) -> dict:
    current_time = datetime.now().astimezone().isoformat()
    
    # 2. 在 Prompt 中示範如何將多個事件拆分進陣列中
    prompt = f"""你是一個精確的時間與意圖解析助手。
請根據當前系統時間，分析使用者的輸入，判斷其意圖（'log' 或 'query'），清洗核心工作內容並「將不同的工作事件拆分為獨立的陣列項目」，最後精確擷取對應的時間資訊。

當前系統時間為：2026-06-01T14:30:00+08:00

【範例 1：單一事件】
使用者輸入：「我昨天下午修正了登入異常的 Bug」
輸出 JSON：
{{
  "intent": "log",
  "clean_contents": ["修正了登入異常的 Bug"],
  "clean_content": "",
  "event_time": "2026-05-31T14:30:00+08:00",
  "query_start_time": null,
  "query_end_time": null
}}

【範例 2：多重事件拆分】
使用者輸入：「早上研究如何解決使用者問題不精確的問題 下午請假」
輸出 JSON：
{{
  "intent": "log",
  "clean_contents": [
    "研究如何解決使用者問題不精確的問題",
    "下午請假"
  ],
  "clean_content": "",
  "event_time": "2026-06-01T14:30:00+08:00",
  "query_start_time": null,
  "query_end_time": null
}}

---

請處理以下實際任務：
當前系統時間為：{current_time}
使用者輸入：「{user_input}」
輸出 JSON："""
    
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=IntentAnalysis,
        ),
    )
    return json.loads(response.text)

def generate_summary(user_query: str, logs: list[dict]) -> str:
    logs_context = "\n".join([f"- [{log.get('event_time', 'unknown')}] {log.get('content')}" for log in logs])
    
    prompt = f"""你是一個專業的工作日誌分析助手。
使用者想查詢："{user_query}"
以下是從資料庫中檢索到的相關工作紀錄：
{logs_context}

請根據以上紀錄，為使用者總結他們的工作內容。如果有多筆紀錄，請條列式呈現，並保持口吻專業且親切。
"""
    
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite',
        contents=prompt
    )
    return response.text
