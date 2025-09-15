"""JSON storage implementation for vector embeddings."""

import json
from pathlib import Path
from typing import Any, Dict, List

from .base import VectorStorage


class JSONVectorStorage(VectorStorage):
    """JSON-based storage for vector embeddings."""

    def save_embeddings(
        self,
        file_id: str,
        embeddings_data: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> Path:
        """Save embeddings data to a JSON file."""
        output_data = {
            "file_id": file_id,
            "embeddings": embeddings_data,
            "metadata": metadata,
            "storage_format": "json",
            "embedding_count": len(embeddings_data),
        }

        file_path = self.storage_path / f"{file_id}_embeddings.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)

        return file_path

    def load_embeddings(self, file_id: str) -> List[Dict[str, Any]]:
        """Load embeddings data from a JSON file."""
        file_path = self.storage_path / f"{file_id}_embeddings.json"

        if not file_path.exists():
            raise FileNotFoundError(f"Embeddings file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("embeddings", [])

    def exists(self, file_id: str) -> bool:
        """Check if embeddings exist for a given file ID."""
        file_path = self.storage_path / f"{file_id}_embeddings.json"
        return file_path.exists()

    def delete(self, file_id: str) -> bool:
        """Delete embeddings for a given file ID."""
        file_path = self.storage_path / f"{file_id}_embeddings.json"

        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def list_files(self) -> List[str]:
        """List all stored file IDs."""
        file_ids = []
        for file_path in self.storage_path.glob("*_embeddings.json"):
            file_id = file_path.stem.replace("_embeddings", "")
            file_ids.append(file_id)

        return sorted(file_ids)

    def get_metadata(self, file_id: str) -> Dict[str, Any]:
        """Get metadata for a specific file."""
        file_path = self.storage_path / f"{file_id}_embeddings.json"

        if not file_path.exists():
            raise FileNotFoundError(f"Embeddings file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("metadata", {})
