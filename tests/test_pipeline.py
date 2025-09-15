"""Tests for the pipeline orchestrator system."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.pipeline import Pipeline, PipelineContext, PipelineStatus, PipelineStep, StepResult, StepStatus
from src.core.pipeline_factory import PipelineFactory
from src.core.pipeline_steps import EmbeddingGenerationStep, FileConversionStep, TextChunkingStep, VectorStorageStep


class TestStep(PipelineStep):
    """Test step for pipeline testing."""

    def __init__(
        self,
        name: str = "test_step",
        should_fail: bool = False,
        should_skip: bool = False,
    ):
        super().__init__(name=name, description="Test step", retry_count=0)
        self.should_fail = should_fail
        self.should_skip_flag = should_skip
        self.execution_count = 0

    def should_skip(self, context: PipelineContext) -> bool:
        return self.should_skip_flag

    async def execute(self, context: PipelineContext) -> StepResult:
        self.execution_count += 1

        if self.should_fail:
            return StepResult(
                status=StepStatus.FAILED,
                message=f"Test step {self.name} failed intentionally",
                error="Simulated failure",
            )

        return StepResult(
            status=StepStatus.SUCCESS,
            message=f"Test step {self.name} completed successfully",
        )


class TestPipeline:
    """Test the pipeline orchestrator functionality."""

    def test_pipeline_creation(self):
        """
        Given: A list of pipeline steps
        When: A pipeline is created
        Then: The pipeline should be properly initialized
        """
        steps = [FileConversionStep()]
        pipeline = Pipeline("test_pipeline", steps)

        assert pipeline.name == "test_pipeline"
        assert len(pipeline.steps) == 1
        assert pipeline.status == PipelineStatus.PENDING
        assert pipeline.current_step_index == 0

    @pytest.mark.asyncio
    async def test_pipeline_execution_success(self):
        """
        Given: A pipeline with a successful step
        When: The pipeline is executed
        Then: The pipeline should complete successfully
        """
        test_step = TestStep(name="success_step", should_fail=False)
        pipeline = Pipeline("test_pipeline", [test_step])

        with tempfile.NamedTemporaryFile() as temp_file:
            context = PipelineContext(
                file_id="test_file",
                email="test@example.com",
                original_filename="test.txt",
                file_path=Path(temp_file.name),
            )

            result = await pipeline.execute(context)

            assert pipeline.status == PipelineStatus.SUCCESS
            assert result["status"] == "success"
            assert result["steps_completed"] == 1
            assert result["steps_failed"] == 0
            assert "success_step" in context.step_results
            assert context.step_results["success_step"].status == StepStatus.SUCCESS
            assert test_step.execution_count == 1

    @pytest.mark.asyncio
    async def test_pipeline_execution_failure(self):
        """
        Given: A pipeline with a failing step
        When: The pipeline is executed
        Then: The pipeline should fail and stop execution
        """
        failing_step = TestStep(name="failing_step", should_fail=True)
        pipeline = Pipeline("test_pipeline", [failing_step])

        with tempfile.NamedTemporaryFile() as temp_file:
            context = PipelineContext(
                file_id="test_file",
                email="test@example.com",
                original_filename="test.txt",
                file_path=Path(temp_file.name),
            )

            result = await pipeline.execute(context)

            assert pipeline.status == PipelineStatus.FAILED
            assert result["status"] == "failed"
            assert result["steps_completed"] == 0
            assert result["steps_failed"] == 1
            assert failing_step.execution_count == 1

    @pytest.mark.asyncio
    async def test_pipeline_step_skipping(self):
        """
        Given: A pipeline with a step that should be skipped
        When: The pipeline is executed
        Then: The step should be skipped and pipeline should continue
        """
        normal_step = TestStep(name="normal_step", should_fail=False)
        skipped_step = TestStep(name="skipped_step", should_skip=True)
        final_step = TestStep(name="final_step", should_fail=False)

        pipeline = Pipeline("test_pipeline", [normal_step, skipped_step, final_step])

        with tempfile.NamedTemporaryFile() as temp_file:
            context = PipelineContext(
                file_id="test_file",
                email="test@example.com",
                original_filename="test.txt",
                file_path=Path(temp_file.name),
            )

            result = await pipeline.execute(context)

            assert pipeline.status == PipelineStatus.SUCCESS
            assert result["status"] == "success"
            assert result["steps_completed"] == 2  # normal_step + final_step
            assert result["steps_failed"] == 0

            # Check execution counts
            assert normal_step.execution_count == 1
            assert skipped_step.execution_count == 0  # Should not execute
            assert final_step.execution_count == 1

            # Check step results
            assert context.step_results["normal_step"].status == StepStatus.SUCCESS
            assert context.step_results["skipped_step"].status == StepStatus.SKIPPED
            assert context.step_results["final_step"].status == StepStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_pipeline_stops_on_failure(self):
        """
        Given: A pipeline with multiple steps where one fails
        When: The pipeline is executed
        Then: Execution should stop at the failing step
        """
        first_step = TestStep(name="first_step", should_fail=False)
        failing_step = TestStep(name="failing_step", should_fail=True)
        never_executed_step = TestStep(name="never_executed", should_fail=False)

        pipeline = Pipeline("test_pipeline", [first_step, failing_step, never_executed_step])

        with tempfile.NamedTemporaryFile() as temp_file:
            context = PipelineContext(
                file_id="test_file",
                email="test@example.com",
                original_filename="test.txt",
                file_path=Path(temp_file.name),
            )

            result = await pipeline.execute(context)

            assert pipeline.status == PipelineStatus.FAILED
            assert result["status"] == "failed"
            assert result["steps_completed"] == 1  # Only first_step
            assert result["steps_failed"] == 1  # failing_step

            # Check execution counts
            assert first_step.execution_count == 1
            assert failing_step.execution_count == 1
            assert never_executed_step.execution_count == 0  # Should not execute

            # Check step results
            assert context.step_results["first_step"].status == StepStatus.SUCCESS
            assert context.step_results["failing_step"].status == StepStatus.FAILED
            assert "never_executed" not in context.step_results


class TestPipelineFactory:
    """Test the pipeline factory functionality."""

    def test_create_full_processing_pipeline(self):
        """
        Given: A request for a full processing pipeline
        When: The factory creates the pipeline
        Then: All expected steps should be included
        """
        pipeline = PipelineFactory.create_full_processing_pipeline()

        assert pipeline.name == "full_file_processing"
        assert len(pipeline.steps) == 4

        step_names = [step.name for step in pipeline.steps]
        expected_steps = [
            "file_conversion",
            "text_chunking",
            "embedding_generation",
            "vector_storage",
        ]

        assert step_names == expected_steps

    def test_create_text_only_pipeline(self):
        """
        Given: A request for a text-only pipeline
        When: The factory creates the pipeline
        Then: Only the conversion step should be included
        """
        pipeline = PipelineFactory.create_text_only_pipeline()

        assert pipeline.name == "text_conversion_only"
        assert len(pipeline.steps) == 1
        assert pipeline.steps[0].name == "file_conversion"

    def test_create_custom_pipeline(self):
        """
        Given: A list of specific step names
        When: A custom pipeline is created
        Then: The pipeline should contain only those steps
        """
        step_names = ["FileConversionStep", "TextChunkingStep"]
        pipeline = PipelineFactory.create_custom_pipeline(step_names)

        assert pipeline.name == "custom_pipeline"
        assert len(pipeline.steps) == 2
        assert pipeline.steps[0].name == "file_conversion"
        assert pipeline.steps[1].name == "text_chunking"

    def test_create_custom_pipeline_invalid_step(self):
        """
        Given: A list containing an invalid step name
        When: A custom pipeline is created
        Then: A ValueError should be raised
        """
        step_names = ["FileConversionStep", "InvalidStep"]

        with pytest.raises(ValueError) as exc_info:
            PipelineFactory.create_custom_pipeline(step_names)

        assert "Unknown step 'InvalidStep'" in str(exc_info.value)

    def test_list_available_pipelines(self):
        """
        Given: A request for available pipelines
        When: The factory lists them
        Then: All expected pipeline types should be returned
        """
        pipelines = PipelineFactory.list_available_pipelines()

        expected_pipelines = [
            "full_processing",
            "text_only",
            "embedding_only",
            "custom",
        ]

        assert pipelines == expected_pipelines

    def test_list_available_steps(self):
        """
        Given: A request for available steps
        When: The factory lists them
        Then: All expected step types should be returned
        """
        steps = PipelineFactory.list_available_steps()

        expected_steps = [
            "FileConversionStep",
            "TextChunkingStep",
            "EmbeddingGenerationStep",
            "VectorStorageStep",
        ]

        assert steps == expected_steps


class TestConcreteSteps:
    """Tests using concrete pipeline steps with minimal mocking."""

    @pytest.mark.asyncio
    async def test_file_conversion_step_with_text_file(self):
        """
        Given: A FileConversionStep and a text file
        When: The step is executed
        Then: The file should be processed successfully
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a test text file
            test_file = temp_path / "test.txt"
            test_file.write_text("This is a test document for conversion.")

            # Mock settings to return our temp directory
            with patch("src.core.pipeline_steps.settings") as mock_settings:
                mock_settings.get_user_raw_uploads_path.return_value = temp_path
                mock_settings.get_user_processed_text_path.return_value = temp_path / "processed"

                # Create context and step
                context = PipelineContext(
                    file_id="test_conversion",
                    email="test@example.com",
                    original_filename="test.txt",
                    file_path=test_file,
                )

                step = FileConversionStep()
                result = await step.execute(context)

                # Verify successful execution
                assert result.status == StepStatus.SUCCESS
                assert "converted successfully" in result.message
                assert "converted_text_path" in context.metadata

    @pytest.mark.asyncio
    async def test_text_chunking_step_with_real_text(self):
        """
        Given: A TextChunkingStep and converted text
        When: The step is executed
        Then: Text should be chunked properly
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a text file with content
            text_file = temp_path / "converted.txt"
            text_content = "This is a test document. " * 100  # Repeat to ensure chunking
            text_file.write_text(text_content)

            # Mock settings
            with patch("src.core.pipeline_steps.settings") as mock_settings:
                mock_settings.get_user_raw_chunks_path.return_value = temp_path / "chunks"
                mock_settings.tiktoken_encoding = "cl100k_base"
                mock_settings.chunk_size = 50
                mock_settings.chunk_overlap_percent = 0.1

                # Create context with converted text path
                context = PipelineContext(
                    file_id="test_chunking",
                    email="test@example.com",
                    original_filename="test.txt",
                    file_path=Path("dummy"),
                    metadata={"converted_text_path": str(text_file)},
                )

                step = TextChunkingStep()
                result = await step.execute(context)

                # Verify successful execution
                assert result.status == StepStatus.SUCCESS
                assert "chunked into" in result.message
                assert "chunks_dir" in context.metadata
                assert "chunk_count" in context.metadata
                assert context.metadata["chunk_count"] > 0

                # Verify chunk files were created
                chunks_dir = Path(context.metadata["chunks_dir"])
                chunk_files = list(chunks_dir.glob("*.txt"))
                assert len(chunk_files) > 0

    @pytest.mark.asyncio
    async def test_text_chunking_step_skips_without_converted_text(self):
        """
        Given: A TextChunkingStep without converted text in context
        When: The step is executed
        Then: The step should be skipped
        """
        context = PipelineContext(
            file_id="test_skip",
            email="test@example.com",
            original_filename="test.txt",
            file_path=Path("dummy"),
            # No converted_text_path in metadata
        )

        step = TextChunkingStep()
        should_skip = step.should_skip(context)

        assert should_skip is True

    @pytest.mark.asyncio
    async def test_embedding_step_skips_without_chunks(self):
        """
        Given: An EmbeddingGenerationStep without chunks in context
        When: The step is executed
        Then: The step should be skipped
        """
        context = PipelineContext(
            file_id="test_skip",
            email="test@example.com",
            original_filename="test.txt",
            file_path=Path("dummy"),
            # No chunks_dir in metadata
        )

        step = EmbeddingGenerationStep()
        should_skip = step.should_skip(context)

        assert should_skip is True

    @pytest.mark.asyncio
    async def test_vector_storage_step_skips_without_embeddings(self):
        """
        Given: A VectorStorageStep without embeddings in context
        When: The step is executed
        Then: The step should be skipped
        """
        context = PipelineContext(
            file_id="test_skip",
            email="test@example.com",
            original_filename="test.txt",
            file_path=Path("dummy"),
            # No embeddings_data in metadata
        )

        step = VectorStorageStep()
        should_skip = step.should_skip(context)

        assert should_skip is True


class TestPipelineIntegration:
    """Integration tests for the complete pipeline system."""

    @pytest.mark.asyncio
    async def test_partial_pipeline_with_real_steps(self):
        """
        Given: A pipeline with file conversion and text chunking steps
        When: The pipeline is executed with a real text file
        Then: Both steps should execute successfully in sequence
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a test file
            test_file = temp_path / "test.txt"
            test_file.write_text("This is a test document for pipeline processing. " * 50)

            # Mock settings for all steps
            with patch("src.core.pipeline_steps.settings") as mock_settings:
                mock_settings.get_user_raw_uploads_path.return_value = temp_path
                mock_settings.get_user_processed_text_path.return_value = temp_path / "processed"
                mock_settings.get_user_raw_chunks_path.return_value = temp_path / "chunks"
                mock_settings.tiktoken_encoding = "cl100k_base"
                mock_settings.chunk_size = 50
                mock_settings.chunk_overlap_percent = 0.1

                # Create context
                context = PipelineContext(
                    file_id="integration_test",
                    email="test@example.com",
                    original_filename="test.txt",
                    file_path=test_file,
                )

                # Create pipeline with first two steps
                pipeline = Pipeline("partial_pipeline", [FileConversionStep(), TextChunkingStep()])

                result = await pipeline.execute(context)

                # Verify pipeline completed successfully
                assert result["status"] == "success"
                assert result["steps_completed"] == 2
                assert result["steps_failed"] == 0

                # Verify step results
                assert context.step_results["file_conversion"].status == StepStatus.SUCCESS
                assert context.step_results["text_chunking"].status == StepStatus.SUCCESS

                # Verify files were created
                assert "converted_text_path" in context.metadata
                assert "chunks_dir" in context.metadata

                chunks_dir = Path(context.metadata["chunks_dir"])
                assert chunks_dir.exists()
                chunk_files = list(chunks_dir.glob("*.txt"))
                assert len(chunk_files) > 0
