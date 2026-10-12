import abc
from typing import List, Dict, Any, Optional


class BaseRetriever(abc.ABC):
    """Abstract interface for contextual retrieval providers in WebSync AI."""

    @abc.abstractmethod
    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve top_k matching document snippets relevant to the query."""
        pass


class InMemoryDocRetriever(BaseRetriever):
    """Safe in-memory document retriever for authorized knowledge contexts."""

    def __init__(self, documents: Optional[List[Dict[str, str]]] = None):
        """Initialize with list of documents: [{'id': '...', 'title': '...', 'content': '...'}]"""
        self.documents: List[Dict[str, str]] = documents or []

    def add_document(self, doc_id: str, title: str, content: str) -> None:
        self.documents.append({"id": doc_id, "title": title, "content": content})

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        if not query or not self.documents:
            return []

        query_terms = set(query.lower().split())
        scored: List[Tuple[float, Dict[str, str]]] = []

        for doc in self.documents:
            content = doc.get("content", "").lower()
            title = doc.get("title", "").lower()
            score = 0.0

            for term in query_terms:
                if term in title:
                    score += 2.0
                if term in content:
                    score += 1.0

            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "id": doc["id"],
                "title": doc.get("title", ""),
                "content": doc.get("content", ""),
                "score": round(score, 2),
            }
            for score, doc in scored[:top_k]
        ]


def format_rag_prompt(
    user_prompt: str,
    retrieved_snippets: List[Dict[str, Any]],
    system_instruction: Optional[str] = None,
) -> Dict[str, Any]:
    """Securely format retrieved reference knowledge into prompt payload.

    SECURITY MEASURE:
    Retrieved content is explicitly isolated inside a structured reference section
    to prevent untrusted content or documents from hijacking system instructions.
    """
    context_blocks = []
    for idx, snippet in enumerate(retrieved_snippets, 1):
        title = snippet.get("title", f"Doc {idx}")
        content = snippet.get("content", "").strip()
        context_blocks.append(f"[Document {idx}: {title}]\n{content}")

    context_str = "\n\n".join(context_blocks)

    augmented_system = (
        (system_instruction or "You are a helpful and truthful AI assistant running on WebSync AI.")
        + "\n\nUse the verified reference documents provided in the context section below to help answer the user query if relevant. "
        "If the answer cannot be determined from the provided context, state that clearly."
    )

    if context_str:
        augmented_prompt = (
            f"=== VERIFIED REFERENCE CONTEXT ===\n"
            f"{context_str}\n"
            f"=== END OF CONTEXT ===\n\n"
            f"=== USER QUERY ===\n"
            f"{user_prompt.strip()}"
        )
    else:
        augmented_prompt = user_prompt.strip()

    return {
        "system": augmented_system,
        "prompt": augmented_prompt,
        "retrieved_count": len(retrieved_snippets),
    }
