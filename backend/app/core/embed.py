"""Embedding client - OpenAI-compatible (works with OpenAI / DashScope / vLLM / Ollama).

We standardize on dim=1024 (matches DB schema). OpenAI text-embedding-3-small
supports the `dimensions` truncation parameter; DashScope text-embedding-v3
is natively 1024.
"""
from __future__ import annotations

from collections.abc import Sequence

from openai import AsyncOpenAI
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import logger


class EmbeddingClient:
    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI | None:
        if not settings.embedding_api_key:
            return None
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.embedding_api_key,
                base_url=settings.embedding_base_url,
            )
        return self._client

    @property
    def enabled(self) -> bool:
        return self.client is not None

    async def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a list of embedding vectors. Raises if disabled."""
        if not self.enabled:
            raise RuntimeError("EMBEDDING_API_KEY not configured")
        if not texts:
            return []

        kwargs = {
            "model": settings.embedding_model,
            "input": list(texts),
        }
        # OpenAI 3-small/large supports `dimensions`. DashScope ignores extras.
        if "text-embedding-3" in settings.embedding_model:
            kwargs["dimensions"] = settings.embedding_dim

        client = self.client
        assert client is not None  # for type-checker

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                resp = await client.embeddings.create(**kwargs)

        vectors = [d.embedding for d in resp.data]
        # Sanity check dimension
        if vectors and len(vectors[0]) != settings.embedding_dim:
            logger.warning(
                "embedding dim mismatch: got {} expected {}",
                len(vectors[0]), settings.embedding_dim,
            )
        return vectors


embedder = EmbeddingClient()
