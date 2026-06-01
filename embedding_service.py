from sentence_transformers import SentenceTransformer

model = SentenceTransformer('intfloat/multilingual-e5-base')

def get_embedding(text: str, is_query: bool = False) -> list[float]:
    prefix = "query: " if is_query else "passage: "
    formatted_text = f"{prefix}{text}"
    
    embedding = model.encode(formatted_text, normalize_embeddings=True)
    return embedding.tolist()