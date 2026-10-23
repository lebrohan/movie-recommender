import ollama

from backend.config import get_embed_model


def ollama_embed_batch(texts: list[str], model: str | None = None) -> list[list[float]]:
    """Embed a list of strings in one Ollama call (model resolved at call time)."""
    return ollama.embed(model=model or get_embed_model(), input=texts)["embeddings"]


def vec_literal(embedding: list[float]) -> str:
    """Format an embedding as a pgvector text literal, e.g. '[0.1,0.2]'."""
    return "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
