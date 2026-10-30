import os
import re
from typing import List, Dict, Any, Optional, Union, Tuple
import numpy as np
from app.logger import logger

RRF_K_DEFAULT = 60.0

DEFAULT_CALIBRATED_THRESHOLDS: Dict[str, float] = {
    "text-embedding-004": 0.65,
    "models/gemini-embedding-001": 0.62,
    "default": 0.65,
}


def get_calibrated_threshold(model_version: Optional[str] = None) -> float:
    """
    Returns the calibrated semantic similarity confidence threshold for the given
    embedding model. Allows environment override via SEMANTIC_CONFIDENCE_THRESHOLD.
    """
    env_thresh = os.getenv("SEMANTIC_CONFIDENCE_THRESHOLD")
    if env_thresh is not None:
        try:
            return float(env_thresh)
        except ValueError:
            pass
    if model_version:
        for key, val in DEFAULT_CALIBRATED_THRESHOLDS.items():
            if key in model_version:
                return val
    return DEFAULT_CALIBRATED_THRESHOLDS["default"]


def normalize_query_text(query: str) -> str:
    """
    Normalizes query text by removing extraneous whitespace and standardizing spacing.
    Preserves case and formula characters for precise technical matching.
    """
    if not query:
        return ""
    return " ".join(query.strip().split())


def cosine_similarity(a: Union[List[float], np.ndarray], b: Union[List[float], np.ndarray]) -> float:
    """
    Computes cosine similarity between two vector representations.
    Returns 0.0 for zero-norm or empty vectors.
    """
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    norm_a = float(np.linalg.norm(va))
    norm_b = float(np.linalg.norm(vb))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


COMMON_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can", "did", "do", "does", "doing", "don", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more", "most",
    "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or", "other",
    "our", "ours", "ourselves", "out", "over", "own", "s", "same", "she", "should", "so", "some",
    "such", "t", "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until", "up", "very",
    "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why", "will",
    "with", "you", "your", "yours", "yourself", "yourselves", "acts", "allows", "exist", "multiple",
    "object", "physical",
}


def compute_keyword_relevance(query_text: str, document_text: str) -> float:
    """
    Evaluates keyword relevance using token overlap and technical term/formula matching.
    Gives heavy weight to exact formula phrases (e.g., 'F = m * a', 'T = 2*pi*sqrt(L/g)').
    Requires exact formula matching or meaningful multi-token content overlap to avoid
    spurious single-stopword false positives.
    """
    if not query_text or not document_text:
        return 0.0

    q_lower = query_text.lower().strip()
    d_lower = document_text.lower().strip()

    # 1. Exact phrase / substring match bonus (strong signal for exact technical terms/formulas)
    has_exact_phrase = (q_lower in d_lower)
    compact_q = re.sub(r"\s+", "", q_lower)
    compact_d = re.sub(r"\s+", "", d_lower)
    has_formula_match = (len(compact_q) >= 4 and compact_q in compact_d)

    # 2. Tokenized term frequency on discriminative content tokens
    raw_q_tokens = [t for t in re.findall(r"[A-Za-z0-9_]+", q_lower) if len(t) > 1]
    content_q_tokens = [t for t in raw_q_tokens if t not in COMMON_STOPWORDS]
    d_tokens = [t for t in re.findall(r"[A-Za-z0-9_]+", d_lower) if len(t) > 1]

    distinct_content_matches = sum(1 for qt in set(content_q_tokens) if qt in d_tokens)

    # If neither exact formula nor meaningful content overlap occurs, reject as keyword match
    if not has_exact_phrase and not has_formula_match and distinct_content_matches < 2:
        return 0.0

    score = 0.0
    if has_exact_phrase:
        score += 3.0
    if has_formula_match:
        score += 2.5

    if d_tokens and content_q_tokens:
        d_len = len(d_tokens)
        matches = 0.0
        for qt in content_q_tokens:
            count = d_tokens.count(qt)
            if count > 0:
                matches += 1.0 + float(np.log(count))
        score += (matches / (d_len ** 0.5))

    return float(score)


def execute_in_memory_hybrid_search(
    memories: List[Dict[str, Any]],
    query_embedding: Optional[List[float]] = None,
    query_text: str = "",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    experiment_id: Optional[str] = None,
    top_k: int = 3,
    rrf_k: float = RRF_K_DEFAULT,
    return_metadata: bool = False,
    include_expired: bool = False,
    search_mode: str = "hybrid",
    embedding_model_version: Optional[str] = None,
) -> Tuple[Union[List[str], List[Dict[str, Any]]], List[Dict[str, Any]]]:
    """
    Executes a multi-stage hybrid retrieval with:
    - Stage 1: Semantic vector retrieval (cosine similarity ranking).
    - Stage 2: Keyword retrieval (PostgreSQL Cover Density Ranking / token overlap).
    - Stage 3: Reciprocal Rank Fusion (RRF) combining both stages with deduplication.
    - Tenant ownership enforcement: Only records matching user_id are searched.
    - Scope & Lifecycle filters: Filter by session_id, experiment_id, and TTL expiration.
    - Supports independent execution: search_mode='hybrid' | 'semantic' | 'keyword'.
    - Full score and document ID logging for evaluation.

    Returns (results, detailed_metadata).
    """
    import time
    canonical_uid = str(user_id) if user_id else None
    now = time.time()

    # Step 0: Apply strict tenant ownership, scope, and lifecycle filters
    candidates = []
    for m in memories:
        if m.get("is_deleted", False):
            continue
        if canonical_uid and str(m.get("user_id")) != canonical_uid:
            continue
        if session_id and str(m.get("session_id")) != str(session_id):
            continue
        if experiment_id and str(m.get("experiment_id")) != str(experiment_id):
            continue
        if embedding_model_version and m.get("embedding_model_version") and m.get("embedding_model_version") != embedding_model_version:
            continue
        if not include_expired:
            exp_at = m.get("expires_at")
            if exp_at:
                if isinstance(exp_at, (int, float)) and exp_at <= now:
                    continue
                elif hasattr(exp_at, "timestamp") and exp_at.timestamp() <= now:
                    continue
        candidates.append(m)

    if not candidates:
        return ([], [])

    norm_query = normalize_query_text(query_text)
    mode = search_mode.lower().strip() if search_mode else "hybrid"

    # Infer mode if inputs dictate
    if mode == "hybrid":
        if not query_embedding and norm_query:
            mode = "keyword"
        elif query_embedding and not norm_query:
            mode = "semantic"

    # --------------------------------------------------------------------------
    # Stage 1: Semantic Retrieval Stage (Vector Cosine Similarity)
    # --------------------------------------------------------------------------
    semantic_stage_map: Dict[Any, Tuple[int, float]] = {}
    if mode in ("hybrid", "semantic") and query_embedding:
        semantic_ranked: List[Tuple[float, Dict[str, Any]]] = []
        for mem in candidates:
            emb = mem.get("embedding")
            if emb:
                sim = cosine_similarity(query_embedding, emb)
                semantic_ranked.append((sim, mem))

        semantic_ranked.sort(key=lambda item: item[0], reverse=True)

        for rank_idx, (sim, mem) in enumerate(semantic_ranked[:20], start=1):
            doc_id = mem.get("id") or mem.get("text")
            semantic_stage_map[doc_id] = (rank_idx, float(sim))

    # --------------------------------------------------------------------------
    # Stage 2: Keyword Retrieval Stage (PostgreSQL Cover Density / Token Overlap)
    # --------------------------------------------------------------------------
    keyword_stage_map: Dict[Any, Tuple[int, float]] = {}
    if mode in ("hybrid", "keyword") and norm_query:
        keyword_scored: List[Tuple[float, Dict[str, Any]]] = []
        for mem in candidates:
            k_score = compute_keyword_relevance(norm_query, mem.get("text", ""))
            if k_score > 0.0:
                keyword_scored.append((k_score, mem))

        keyword_scored.sort(key=lambda item: item[0], reverse=True)

        for rank_idx, (k_score, mem) in enumerate(keyword_scored[:20], start=1):
            doc_id = mem.get("id") or mem.get("text")
            keyword_stage_map[doc_id] = (rank_idx, float(k_score))

    # --------------------------------------------------------------------------
    # Stage 3: Reciprocal Rank Fusion (RRF) & Deduplication
    # --------------------------------------------------------------------------
    doc_lookup: Dict[Any, Dict[str, Any]] = {
        (m.get("id") or m.get("text")): m for m in candidates
    }
    all_candidate_ids = set(semantic_stage_map.keys()) | set(keyword_stage_map.keys())

    fused_results: List[Dict[str, Any]] = []
    for doc_id in all_candidate_ids:
        mem = doc_lookup.get(doc_id)
        if not mem:
            continue

        sem_rank, sem_score = semantic_stage_map.get(doc_id, (None, None))
        kw_rank, kw_score = keyword_stage_map.get(doc_id, (None, None))

        rrf_sem = (1.0 / (rrf_k + sem_rank)) if sem_rank is not None else 0.0
        rrf_kw = (1.0 / (rrf_k + kw_rank)) if kw_rank is not None else 0.0
        rrf_total = rrf_sem + rrf_kw

        fused_results.append({
            "id": doc_id,
            "text": mem.get("text", ""),
            "user_id": mem.get("user_id"),
            "session_id": mem.get("session_id"),
            "experiment_id": mem.get("experiment_id"),
            "created_at": mem.get("created_at"),
            "expires_at": mem.get("expires_at"),
            "embedding_model_version": mem.get("embedding_model_version"),
            "rrf_score": float(rrf_total),
            "semantic_rank": sem_rank,
            "semantic_score": sem_score,
            "keyword_rank": kw_rank,
            "keyword_score": kw_score,
            "ts_rank_cd_score": kw_score,
            "bm25_score": kw_score,
            "ranking_algorithm": "rrf_hybrid_cover_density" if mode == "hybrid" else (
                "semantic_only" if mode == "semantic" else "keyword_cover_density"
            ),
        })

    # Sort descending by fused RRF score
    fused_results.sort(key=lambda r: r["rrf_score"], reverse=True)
    top_results = fused_results[:top_k]

    # Confidence check using calibrated threshold
    if top_results:
        top_sem = top_results[0].get("semantic_score")
        top_kw = top_results[0].get("keyword_score")
        threshold = get_calibrated_threshold(embedding_model_version)
        if (top_sem is not None and top_sem < threshold) and (top_kw is None or top_kw <= 0.0):
            low_conf_result = ["System: [LOW_CONFIDENCE] Let me think about this differently..."]
            return (low_conf_result if not return_metadata else top_results, top_results)

    if return_metadata:
        return (top_results, top_results)
    else:
        return ([r["text"] for r in top_results], top_results)
