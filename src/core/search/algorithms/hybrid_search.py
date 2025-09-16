"""
Hybrid search algorithm combining cosine similarity with keyword matching.
"""

import re
from collections import Counter
from math import log
from typing import Dict, List, Optional

from ...domain import Chunk, Vector
from ..query import ChunkSearchResult
from .base_search import BaseSearchAlgorithm


class HybridSearchAlgorithm(BaseSearchAlgorithm):
    """
    Hybrid search algorithm combining vector similarity with keyword matching.

    Uses a weighted combination of:
    1. Cosine similarity between embeddings (semantic similarity)
    2. BM25-like keyword matching (lexical similarity)

    This provides both semantic understanding and exact keyword matching.
    """

    def __init__(self, cosine_weight: float = 0.7, keyword_weight: float = 0.3):
        """
        Initialize hybrid search algorithm.

        Args:
            cosine_weight: Weight for cosine similarity component (0.0 to 1.0)
            keyword_weight: Weight for keyword matching component (0.0 to 1.0)
        """
        if cosine_weight < 0 or cosine_weight > 1:
            raise ValueError("Cosine weight must be between 0.0 and 1.0")

        if keyword_weight < 0 or keyword_weight > 1:
            raise ValueError("Keyword weight must be between 0.0 and 1.0")

        if abs(cosine_weight + keyword_weight - 1.0) > 1e-6:
            raise ValueError("Cosine weight and keyword weight must sum to 1.0")

        self.cosine_weight = cosine_weight
        self.keyword_weight = keyword_weight

    def search(
        self, query_vector: Vector, chunks: List[Chunk], limit: int, query_text: Optional[str] = None
    ) -> List[ChunkSearchResult]:
        """
        Search using hybrid algorithm.

        Args:
            query_vector: The vector representation of the search query
            chunks: List of chunks to search through (must have embeddings)
            limit: Maximum number of results to return

        Returns:
            List of ChunkSearchResult objects, ranked by hybrid score
        """
        self._validate_inputs(query_vector, chunks, limit)

        if query_text is None:
            query_text = ""

        valid_chunks = self._filter_valid_chunks(chunks)

        cosine_scores = []
        for chunk in valid_chunks:
            assert chunk.embedding is not None  # Already validated in _filter_valid_chunks
            similarity = chunk.embedding.cosine_similarity(query_vector)
            cosine_scores.append(similarity)

        keyword_scores = self._calculate_keyword_scores(query_text, valid_chunks)

        hybrid_scores = []
        for cosine_score, keyword_score in zip(cosine_scores, keyword_scores):
            hybrid_score = (self.cosine_weight * cosine_score) + (self.keyword_weight * keyword_score)
            hybrid_scores.append(hybrid_score)

        return self._create_search_results(valid_chunks, hybrid_scores, limit)

    def _calculate_keyword_scores(self, query_text: str, chunks: List[Chunk]) -> List[float]:
        """
        Calculate keyword matching scores using BM25-like algorithm.

        Args:
            query_text: The original query text
            chunks: List of chunks to score

        Returns:
            List of keyword matching scores (0.0 to 1.0)
        """
        if not query_text.strip():
            return [0.0] * len(chunks)

        query_keywords = self._extract_keywords(query_text)

        if not query_keywords:
            return [0.0] * len(chunks)

        doc_frequencies = self._calculate_document_frequencies(query_keywords, chunks)

        # Calculate BM25-like scores for each chunk
        scores = []
        total_docs = len(chunks)

        for chunk in chunks:
            chunk_keywords = self._extract_keywords(chunk.text)
            chunk_keyword_counts = Counter(chunk_keywords)

            score = 0.0
            for keyword in query_keywords:
                if keyword in chunk_keyword_counts:
                    # Term frequency in document
                    tf = chunk_keyword_counts[keyword]

                    # Document frequency (number of documents containing the term)
                    df = doc_frequencies.get(keyword, 0)

                    # Inverse document frequency with smoothing for small collections
                    if df > 0:
                        idf = log((total_docs - df + 0.5) / (df + 0.5))
                        # Add minimum IDF for small collections to avoid 0 scores
                        if idf <= 0 and total_docs <= 10:
                            idf = 0.1  # Small positive value for relevance
                    else:
                        idf = 0

                    # BM25-like scoring (simplified)
                    k1 = 1.2  # Term frequency saturation parameter
                    score += idf * (tf * (k1 + 1)) / (tf + k1)

            scores.append(score)

        # Normalize scores to 0-1 range
        if scores:
            min_score = min(scores)
            max_score = max(scores)

            # Handle negative scores by shifting to positive range
            if min_score < 0:
                scores = [score - min_score for score in scores]
                max_score = max_score - min_score

            # Normalize to 0-1 range
            if max_score > 0:
                scores = [score / max_score for score in scores]

        return scores

    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract keywords from text.

        Args:
            text: Input text

        Returns:
            List of lowercase keywords
        """
        # Simple keyword extraction: lowercase, remove punctuation, split on whitespace
        # Filter out common stop words and short words
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "this",
            "that",
            "these",
            "those",
        }

        cleaned_text = re.sub(r"[^\w\s]", " ", text.lower())

        words = cleaned_text.split()
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]

        return keywords

    def _calculate_document_frequencies(self, keywords: List[str], chunks: List[Chunk]) -> Dict[str, int]:
        """
        Calculate how many documents contain each keyword.

        Args:
            keywords: List of keywords to check
            chunks: List of chunks to analyze

        Returns:
            Dictionary mapping keyword to document frequency
        """
        doc_frequencies = {}

        for keyword in keywords:
            count = 0
            for chunk in chunks:
                chunk_keywords = set(self._extract_keywords(chunk.text))
                if keyword in chunk_keywords:
                    count += 1
            doc_frequencies[keyword] = count

        return doc_frequencies

    def get_algorithm_name(self) -> str:
        return "hybrid"
