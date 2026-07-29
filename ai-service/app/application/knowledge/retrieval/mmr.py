import logging
import math

logger = logging.getLogger(__name__)


def mmr_rerank(
    query_embedding: list[float],
    candidate_embeddings: list[list[float]],
    candidate_scores: list[float],
    top_k: int,
    lambda_param: float = 0.7,
) -> list[int]:
    if not candidate_embeddings or not candidate_scores:
        return []

    if len(candidate_embeddings) != len(candidate_scores):
        raise ValueError("candidate_embeddings and candidate_scores must have the same length")

    n = len(candidate_embeddings)
    selected: list[int] = []
    remaining = set(range(n))

    for _ in range(min(top_k, n)):
        if not remaining:
            break

        best_score = -1.0
        best_idx = -1

        for i in remaining:
            sim_to_query = candidate_scores[i]

            if selected:
                max_sim_to_selected = max(
                    _cosine_similarity(candidate_embeddings[i], candidate_embeddings[j])
                    for j in selected
                )
            else:
                max_sim_to_selected = 0.0

            mmr_score = lambda_param * sim_to_query - (1 - lambda_param) * max_sim_to_selected

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i

        if best_idx != -1:
            selected.append(best_idx)
            remaining.remove(best_idx)

    return selected


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(ai * bi for ai, bi in zip(a, b))
    norm_a = math.sqrt(sum(ai * ai for ai in a))
    norm_b = math.sqrt(sum(bi * bi for bi in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
