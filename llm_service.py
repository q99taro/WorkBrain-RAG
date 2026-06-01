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
    prompt = f"""你是一個精確的時間與意圖解析助手，特別擅長理解 AI 工程師或軟體開發者的技術日誌。
請根據當前系統時間，分析使用者的輸入，判斷其意圖（'log' 或 'query'），清洗核心工作內容並「將不同的工作事件拆分為獨立的陣列項目」，最後精確擷取對應的時間資訊。

**重要邏輯說明：**
1. **技術一致性**：若使用者描述的是「將 X 改為 Y」或「為了 A 而移除 B」等具有邏輯因果、技術替代關係的描述，請將其視為「單一工作事件」，不要拆散。
2. **多重事件**：只有當描述的是完全不同的活動（例如：研究 A、然後開會 B、最後處理 C）時，才拆分為陣列的不同項目。

當前系統時間為：2026-06-01T14:30:00+08:00

【範例 1：技術替代（單一事件）】
使用者輸入：「我上禮拜一也把 postgres 連線池拿掉 改成使用null pool」
輸出 JSON：
{{
  "intent": "log",
  "clean_contents": ["將 Postgres 連線池移除並改用 NullPool"],
  "clean_content": "",
  "event_time": "2026-05-25T14:30:00+08:00",
  "query_start_time": null,
  "query_end_time": null
}}

【範例 2：多重活動（拆分事件）】
使用者輸入：「上午研究如何解決 embedding 不精確問題，下午請假」
輸出 JSON：
{{
  "intent": "log",
  "clean_contents": [
    "研究如何解決 embedding 不精確問題",
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
    
    prompt = f"""你是一個專業且精簡的工作日誌助手。
使用者想查詢："{user_query}"
以下是相關的工作紀錄：
{logs_context}

請根據紀錄，用最精簡的口吻回答。
規則：
1. 如果是列出某天的紀錄，格式為：「你在 [日期] [星期] 做了這些事情：」後接條列項目。
2. 如果是回答特定問題，格式為：「你是在 [日期] [星期] 針對 [對象] 做了 [動作] 的優化/處理。」
3. 除非使用者詢問，否則不要輸出多餘的問候語。

回答範例：
你在 6/1 星期一 做了這些事情：
1. 修正登入 Bug
2. 優化 Embedding 檢索邏輯

你是在 3/12 星期四 針對 Postgres 連線池做了 NullPool 的優化。
"""
    
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite',
        contents=prompt
    )
    return response.text
