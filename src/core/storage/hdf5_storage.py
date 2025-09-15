"""HDF5 storage implementation for vector embeddings."""

import json
from pathlib import Path
from typing import Any, Dict, List

import h5py
import numpy as np

from .base import VectorStorage


class HDF5VectorStorage(VectorStorage):
    """HDF5-based storage for vector embeddings.

    HDF5 is optimized for numerical data and provides:
    - Efficient storage of large arrays
    - Compression support
    - Fast random access
    - Cross-platform compatibility
    """

    def save_embeddings(
        self,
        file_id: str,
        embeddings_data: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> Path:
        file_path = self.storage_path / f"{file_id}_embeddings.h5"

        embeddings = [item["embedding"] for item in embeddings_data]
        texts = [item["text"] for item in embeddings_data]
        filenames = [item["filename"] for item in embeddings_data]
        token_counts = [item["token_count"] for item in embeddings_data]
        embedding_models = [
            item.get("embedding_model", "unknown") for item in embeddings_data
        ]

        embeddings_array = np.array(embeddings, dtype=np.float32)

        with h5py.File(file_path, "w") as f:
            f.create_dataset(
                "embeddings",
                data=embeddings_array,
                compression="gzip",
                compression_opts=9,
                shuffle=True,
                fletcher32=True,  # Checksum for data integrity
            )

            text_dtype = h5py.string_dtype(encoding="utf-8")
            f.create_dataset("texts", data=texts, dtype=text_dtype)
            f.create_dataset("filenames", data=filenames, dtype=text_dtype)
            f.create_dataset(
                "embedding_models", data=embedding_models, dtype=text_dtype
            )

            f.create_dataset("token_counts", data=token_counts, dtype=np.int32)

            file_metadata = {
                "file_id": file_id,
                "embedding_count": len(embeddings_data),
                "embedding_dimension": len(embeddings[0]) if embeddings else 0,
                "storage_format": "hdf5",
                "metadata": metadata,
            }

            for key, value in file_metadata.items():
                if isinstance(value, dict):
                    f.attrs[key] = json.dumps(value)
                else:
                    f.attrs[key] = value

        return file_path

    def load_embeddings(self, file_id: str) -> List[Dict[str, Any]]:
        """Load embeddings data from an HDF5 file."""
        file_path = self.storage_path / f"{file_id}_embeddings.h5"

        if not file_path.exists():
            raise FileNotFoundError(f"Embeddings file not found: {file_path}")

        embeddings_data = []

        with h5py.File(file_path, "r") as f:
            embeddings = f["embeddings"][:]
            texts = f["texts"][:]
            filenames = f["filenames"][:]
            token_counts = f["token_counts"][:]
            embedding_models = f["embedding_models"][:]

            for i in range(len(embeddings)):
                embeddings_data.append(
                    {
                        "filename": (
                            filenames[i].decode("utf-8")
                            if isinstance(filenames[i], bytes)
                            else str(filenames[i])
                        ),
                        "text": (
                            texts[i].decode("utf-8")
                            if isinstance(texts[i], bytes)
                            else str(texts[i])
                        ),
                        "token_count": int(token_counts[i]),
                        "embedding": embeddings[
                            i
                        ].tolist(),  # Convert numpy array back to list
                        "embedding_model": (
                            embedding_models[i].decode("utf-8")
                            if isinstance(embedding_models[i], bytes)
                            else str(embedding_models[i])
                        ),
                    }
                )

        return embeddings_data

    def exists(self, file_id: str) -> bool:
        """Check if embeddings exist for a given file ID."""
        file_path = self.storage_path / f"{file_id}_embeddings.h5"
        return file_path.exists()

    def delete(self, file_id: str) -> bool:
        """Delete embeddings for a given file ID."""
        file_path = self.storage_path / f"{file_id}_embeddings.h5"

        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def list_files(self) -> List[str]:
        """List all stored file IDs."""
        file_ids = []
        for file_path in self.storage_path.glob("*_embeddings.h5"):
            # Extract file_id from filename (remove _embeddings.h5 suffix)
            file_id = file_path.stem.replace("_embeddings", "")
            file_ids.append(file_id)

        return sorted(file_ids)

    def get_metadata(self, file_id: str) -> Dict[str, Any]:
        """Get metadata for a specific file."""
        file_path = self.storage_path / f"{file_id}_embeddings.h5"

        if not file_path.exists():
            raise FileNotFoundError(f"Embeddings file not found: {file_path}")

        with h5py.File(file_path, "r") as f:
            metadata_str = f.attrs.get("metadata", "{}")
            return json.loads(metadata_str)

    def get_embeddings_array(self, file_id: str) -> np.ndarray:
        """Get embeddings as a numpy array for efficient computation."""
        file_path = self.storage_path / f"{file_id}_embeddings.h5"

        if not file_path.exists():
            raise FileNotFoundError(f"Embeddings file not found: {file_path}")

        with h5py.File(file_path, "r") as f:
            return f["embeddings"][:]

    def get_file_info(self, file_id: str) -> Dict[str, Any]:
        """Get comprehensive file information including dimensions and compression stats."""
        file_path = self.storage_path / f"{file_id}_embeddings.h5"

        if not file_path.exists():
            raise FileNotFoundError(f"Embeddings file not found: {file_path}")

        with h5py.File(file_path, "r") as f:
            embeddings_dataset = f["embeddings"]

            info = {
                "file_id": f.attrs.get("file_id"),
                "file_path": str(file_path),
                "file_size_bytes": file_path.stat().st_size,
                "embedding_count": f.attrs.get("embedding_count"),
                "embedding_dimension": f.attrs.get("embedding_dimension"),
                "storage_format": f.attrs.get("storage_format"),
                "compression": embeddings_dataset.compression,
                "compression_opts": embeddings_dataset.compression_opts,
                "shape": embeddings_dataset.shape,
                "dtype": str(embeddings_dataset.dtype),
                "metadata": json.loads(f.attrs.get("metadata", "{}")),
            }

        return info
