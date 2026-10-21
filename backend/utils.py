import ollama

from backend.config import EMBED_MODEL


def ollama_embed_batch(texts: list[str], model: str = EMBED_MODEL) -> list[list[float]]:
    """Embed a list of strings in one Ollama call."""
    return ollama.embed(model=model, input=texts)["embeddings"]


def vec_literal(embedding: list[float]) -> str:
    """Format an embedding as a pgvector text literal, e.g. '[0.1,0.2]'."""
    return "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
