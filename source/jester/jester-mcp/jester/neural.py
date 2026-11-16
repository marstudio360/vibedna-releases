"""
Jester Neural Layer: local embeddings + cosine re-ranking.
Uses model2vec (pure NumPy at inference, ~30MB model, no PyTorch).

Two roles:
  1. neural_rerank: take N candidates from any free source, return top K by semantic similarity
  2. embed: produce vectors for the personal_index
"""

import blas_threads  # noqa: F401  must precede numpy, see module docstring
import numpy as np
from pathlib import Path

from paths import embed_model_dir
EMBED_MODEL_DIR = embed_model_dir()

_MODEL_NAME = "minishlab/potion-base-8M"
_MODEL = None


def _get_model():
    """Lazy-load the static embedding model. First call downloads ~30MB."""
    global _MODEL
    if _MODEL is None:
        from model2vec import StaticModel
        import os
        os.environ.setdefault("HF_HOME", str(EMBED_MODEL_DIR))
        _MODEL = StaticModel.from_pretrained(_MODEL_NAME)
    return _MODEL


def embed(texts: list[str]) -> np.ndarray:
    """Embed a list of texts to (N, D) numpy array. Vectors are L2-normalized."""
    if not texts:
        return np.zeros((0, 256), dtype=np.float32)
    model = _get_model()
    vectors = model.encode(texts)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (vectors / norms).astype(np.float32)


def cosine_rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
    text_key: str = "content",
    title_key: str = "title",
) -> list[dict]:
    """Re-rank candidate dicts by semantic similarity to query.
    Each candidate dict should have a `content` (and ideally `title`) field.
    Returns top_k candidates with `_neural_score` added."""
    if not candidates:
        return []

    docs = []
    for c in candidates:
        title = c.get(title_key, "") or ""
        content = c.get(text_key, "") or ""
        # title weighted by appearing twice
        docs.append(f"{title} {title} {content}"[:2000])

    q_vec = embed([query])
    d_vecs = embed(docs)
    scores = (d_vecs @ q_vec.T).flatten()

    ranked_idx = np.argsort(-scores)[:top_k]
    out = []
    for i in ranked_idx:
        c = dict(candidates[int(i)])
        c["_neural_score"] = float(scores[int(i)])
        out.append(c)
    return out
