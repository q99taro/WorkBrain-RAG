import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def insert_log(user_id: str, content: str, embedding: list[float], event_time: str = None) -> bool:
    data = {
        "user_id": user_id,
        "content": content,
        "embedding": embedding
    }
    
    if event_time:
        data["event_time"] = event_time
        
    response = supabase.table("work_logs").insert(data).execute()
    return len(response.data) > 0

def search_logs(user_id: str, query_embedding: list[float], start_time: str, end_time: str, top_k: int = 8, threshold: float = 0.7) -> list[dict]:
    response = supabase.rpc(
        "match_work_logs",
        {
            "query_embedding": query_embedding,
            "match_threshold": threshold,
            "match_count": top_k,
            "p_user_id": user_id,
            "p_start_time": start_time,
            "p_end_time": end_time
        }
    ).execute()
    
    return response.data