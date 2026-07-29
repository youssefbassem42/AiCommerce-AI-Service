import hashlib

from app.application.knowledge.retrieval.dto import RetrievedChunkDTO


def _content_fingerprint(text: str) -> str:
    return hashlib.md5(text[:200].encode("utf-8")).hexdigest()


def deduplicate_chunks(
    chunks: list[RetrievedChunkDTO],
) -> list[RetrievedChunkDTO]:
    if not chunks:
        return chunks

    seen_fingerprints: set[str] = set()
    seen_ids: set[str] = set()
    result: list[RetrievedChunkDTO] = []

    for c in chunks:
        fp = _content_fingerprint(c.content)
        if fp in seen_fingerprints:
            continue
        if c.chunk_id in seen_ids:
            continue
        seen_fingerprints.add(fp)
        seen_ids.add(c.chunk_id)
        result.append(c)

    return result
