import os
import json
from datetime import datetime
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class IntentAnalysis(BaseModel):
    intent: str = Field(description="Must be 'log' for recording work, or 'query' for asking questions about past work.")
    clean_content: str = Field(description="The core content of the user's message, removing time adverbs.")
    event_time: Optional[str] = Field(description="If intent is 'log', extract the specific ISO 8601 time. Return null if not specified.")
    query_start_time: Optional[str] = Field(description="If intent is 'query', extract the start of the requested time range in ISO 8601 format.")
    query_end_time: Optional[str] = Field(description="If intent is 'query', extract the end of the requested time range in ISO 8601 format.")

def analyze_intent(user_input: str) -> dict:
    current_time = datetime.now().astimezone().isoformat()
    
    prompt = f"""你是一個精確的時間與意圖解析助手。
請根據當前系統時間，分析使用者的輸入，判斷其意圖（'log' 或 'query'），清洗核心工作內容，並精確擷取對應的時間資訊。

當前系統時間為：2026-06-01T14:30:00+08:00

【範例】
使用者輸入：「我昨天下午修正了登入異常的 Bug」
輸出 JSON：
{{
  "intent": "log",
  "clean_content": "修正了登入異常的 Bug",
  "event_time": "2026-05-31T14:30:00+08:00",
  "query_start_time": null,
  "query_end_time": null
}}

---

請處理以下實際任務：
當前系統時間為：{current_time}
使用者輸入：「{user_input}」
輸出 JSON："""
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=IntentAnalysis,
        ),
    )
    return json.loads(response.text)

def generate_summary(user_query: str, retrieved_logs: list[dict]) -> str:
    context_lines = []
    for log in retrieved_logs:
        time_str = log.get('event_time', '未知時間')
        content = log.get('content', '')
        context_lines.append(f"[{time_str}] {content}")
    
    context_text = "\n".join(context_lines)
    
    prompt = f"""你是一個專業且條理分明的年資/工作日誌摘要助理。
請根據以下提供的歷史紀錄（Context）來回答使用者的問題。

【輸出格式嚴格規範】
1. 必須將工作紀錄依照「日期」由舊到新（或由新到舊，依習慣）進行分組。
2. 每一天必須獨立為一個標題，格式統一為：「M/D 星期X」，例如：「6/1 星期一」。
3. 該日期下方的具體工作事項，必須使用數字列表「1.」、「2.」進行條列。
4. 若 Context 中沒有相關或足夠的資訊，請誠實告知，絕對不要自行編造。

【輸出範例】
6/1 星期一
1. 修正了登入頁面異常的 Bug
2. 與前端工程師對接 API 規格

6/2 星期二
1. 完成工作日誌 LineBot 的資料庫建置
2. 進行 Embedding 模型效能測試

---

[Context]
{context_text}

[使用者問題]
{user_query}
"""
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text