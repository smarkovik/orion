"""Factory for creating different pipeline configurations."""

from typing import Dict, List, Type

from .pipeline import Pipeline, PipelineStep
from .pipeline_steps import (
    EmbeddingGenerationStep,
    FileConversionStep,
    TextChunkingStep,
    VectorStorageStep,
)


class PipelineFactory:
    """Factory for creating pre-configured pipelines."""

    @staticmethod
    def create_full_processing_pipeline() -> Pipeline:
        """Create the complete file processing pipeline.

        Steps:
        1. Convert file to text
        2. Chunk text into smaller pieces
        3. Generate embeddings using Cohere
        4. Store embeddings in vector database
        """
        steps: List[PipelineStep] = [
            FileConversionStep(),
            TextChunkingStep(),
            EmbeddingGenerationStep(),
            VectorStorageStep(),
        ]

        return Pipeline(name="full_file_processing", steps=steps)

    @staticmethod
    def create_text_only_pipeline() -> Pipeline:
        """Create a pipeline that only converts files to text.

        Steps:
        1. Convert file to text
        """
        steps: List[PipelineStep] = [
            FileConversionStep(),
        ]

        return Pipeline(name="text_conversion_only", steps=steps)

    @staticmethod
    def create_embedding_pipeline() -> Pipeline:
        """Create a pipeline for text chunking and embedding generation.

        Assumes text conversion has already been done.

        Steps:
        1. Chunk text into smaller pieces
        2. Generate embeddings using Cohere
        3. Store embeddings in vector database
        """
        steps: List[PipelineStep] = [
            TextChunkingStep(),
            EmbeddingGenerationStep(),
            VectorStorageStep(),
        ]

        return Pipeline(name="embedding_generation", steps=steps)

    @staticmethod
    def create_custom_pipeline(step_names: List[str]) -> Pipeline:
        """Create a custom pipeline from a list of step names.

        Args:
            step_names: List of step class names to include

        Returns:
            Pipeline with the specified steps

        Raises:
            ValueError: If any step name is not recognized
        """
        step_mapping: Dict[str, Type[PipelineStep]] = {
            "FileConversionStep": FileConversionStep,
            "TextChunkingStep": TextChunkingStep,
            "EmbeddingGenerationStep": EmbeddingGenerationStep,
            "VectorStorageStep": VectorStorageStep,
        }

        steps: List[PipelineStep] = []
        for step_name in step_names:
            if step_name not in step_mapping:
                available_steps = list(step_mapping.keys())
                raise ValueError(
                    f"Unknown step '{step_name}'. Available steps: {available_steps}"
                )

            step_class = step_mapping[step_name]
            # mypy can't infer that these are concrete classes, not abstract
            steps.append(step_class())  # type: ignore[call-arg]

        return Pipeline(name="custom_pipeline", steps=steps)

    @staticmethod
    def list_available_pipelines() -> List[str]:
        """List all available pre-configured pipelines."""
        return ["full_processing", "text_only", "embedding_only", "custom"]

    @staticmethod
    def list_available_steps() -> List[str]:
        """List all available pipeline steps."""
        return [
            "FileConversionStep",
            "TextChunkingStep",
            "EmbeddingGenerationStep",
            "VectorStorageStep",
        ]
