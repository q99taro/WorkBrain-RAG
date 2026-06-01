# 🤖 Time-Aware Smart Work-Log RAG System
> 專為個人工作日誌設計的智慧檢索與摘要系統，整合 LLM 意圖解析、語意分塊與非同步架構，解決真實 RAG 系統落地的常見痛點。

[![Application Status](https://img.shields.io/badge/Hugging%20Face-Running-green)](https://huggingface.co/spaces/q9jotaro/W_Log)
[![Backend Framework](https://img.shields.io/badge/Framework-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![Database](https://img.shields.io/badge/Database-Supabase%20%28pgvector%29-3ECF8E)](https://supabase.com/)

## 🚀 系統架構 (Architecture)

本系統部署於 Hugging Face Spaces，透過 FastAPI 接收 LINE Webhook，並採用非同步工作流進行 RAG 檢索與生成。

```mermaid
graph TD
    User([LINE 使用者]) -->|1. 發送訊息| LineServer[LINE Platform]
    LineServer -->|2. Webhook POST| FastAPI[FastAPI Gateway]
    
    subgraph FastAPI Backend
        FastAPI -->|3. Async Flow 解耦| Router{Hybrid Router}
        Router -->|A. 前綴規則攔截| LocalProcess[Python 本地端處理]
        Router -->|B. 自然語言輸入| Gemini[Gemini 2.5 Flash API]
        
        Gemini -->|4. Intent & Time JSON| MainWorkflow[RAG Workflow]
        LocalProcess -->|4. 封裝陣列| MainWorkflow
        
        MainWorkflow -->|5. For 迴圈迭代分塊| EmbedModel[本地端 mE5-base Embedding]
    end

    EmbedModel -->|6. 向量寫入 / 混合檢索| Supabase[(Supabase pgvector)]
    Supabase -->|7. 歷史日誌回傳| MainWorkflow
    MainWorkflow -->|8. 重排與條列摘要生成| Gemini
    MainWorkflow -->|9. 非同步主動推播| LineServer