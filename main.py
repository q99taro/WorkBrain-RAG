import os
import sys
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

import embedding_service
import database_service
import llm_service

load_dotenv()

app = FastAPI()

channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('LINE_CHANNEL_SECRET')

if channel_access_token is None or channel_secret is None:
    sys.exit(1)

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def generate_summary_with_retry(user_query, logs):
    return llm_service.generate_summary(user_query, logs)

def async_rag_workflow(user_id: str, user_text: str):
    reply_text = ""
    try:
        intent = "unknown"
        clean_content = user_text
        clean_contents = []
        event_time = None
        query_start = None
        query_end = None
        intent_data = {}

        if user_text.startswith(("log", "紀錄", "記錄")):
            intent = "log"
            prefix_len = 3 if user_text.lower().startswith("log") else 2
            content_str = user_text[prefix_len:].strip()
            if content_str:
                intent_data = llm_service.analyze_intent(content_str)
                clean_contents = intent_data.get("clean_contents", [])
                if not clean_contents:
                    clean_contents = [content_str]
                event_time = intent_data.get("event_time")
        elif user_text.strip() in ("?", "？"):
            # 單純輸入問號時的預設快速查詢（只抓昨天的紀錄）
            intent = "query"
            now = datetime.now()
            yesterday = now - timedelta(days=1)
            query_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            query_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
            clean_content = "我昨天做了什麼"
        else:
            intent_data = llm_service.analyze_intent(user_text)
            intent = intent_data.get("intent")
            clean_contents = intent_data.get("clean_contents", [])
            clean_content = intent_data.get("clean_content")
            if not clean_content:
                clean_content = user_text
            event_time = intent_data.get("event_time")
            query_start = intent_data.get("query_start_time")
            query_end = intent_data.get("query_end_time")

        if intent == "log":
            if not clean_contents and intent_data:
                clean_contents = intent_data.get("clean_contents", [])
                
            success_count = 0
            fail_count = 0

            for content in clean_contents:
                vector = embedding_service.get_embedding(content, is_query=False)
                
                success = database_service.insert_log(
                    user_id=user_id,
                    content=content,
                    embedding=vector,
                    event_time=event_time
                )
                
                if success:
                    success_count += 1
                else:
                    fail_count += 1

            if fail_count == 0 and success_count > 0:
                reply_text = f"✅ 已成功為您記錄 {success_count} 筆工作項目。"
            elif success_count > 0 and fail_count > 0:
                reply_text = f"⚠️ 部分記錄成功 ({success_count} 筆)，但有 {fail_count} 筆記錄失敗，請檢查資料庫狀態。"
            elif success_count == 0 and fail_count == 0:
                reply_text = "請輸入您要記錄的工作內容。"
            else:
                reply_text = "❌ 記錄失敗，請檢查資料庫連線。"

        elif intent == "query":
            # 若 LLM 判定為模糊時間並回傳 None，給定極大的預設值以避免資料庫 RPC 對 NULL 比較時回傳 false
            safe_query_start = query_start if query_start else "1970-01-01T00:00:00+00:00"
            safe_query_end = query_end if query_end else "2100-01-01T23:59:59+00:00"
            
            vector = embedding_service.get_embedding(clean_content, is_query=True)
            retrieved_logs = database_service.search_logs(
                user_id=user_id,
                query_embedding=vector,
                start_time=safe_query_start,
                end_time=safe_query_end,
                top_k=10,
                threshold=0.6
            )
            
            if not retrieved_logs:
                reply_text = "這段時間內沒有找到相關的工作紀錄喔。"
            else:
                reply_text = generate_summary_with_retry(clean_content, retrieved_logs)
        
        else:
            reply_text = "抱歉，我無法辨識您的意圖，請明確告訴我您要記錄工作還是查詢日誌。"

    except Exception as e:
        reply_text = f"Error in RAG workflow: {str(e)}"
        
    finally:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=reply_text)]
                )
            )

@app.get("/")
async def index():
    return {"status": "working"}

@app.post("/")
async def index_post(request: Request, background_tasks: BackgroundTasks):
    return await callback(request, background_tasks)

@app.post("/callback")
async def callback(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get('X-Line-Signature', '')
    body = await request.body()
    body_str = body.decode('utf-8')

    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text
    
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, async_rag_workflow, user_id, user_text)