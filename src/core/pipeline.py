"""Pipeline orchestrator for file processing workflows."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Type

from .logging import get_logger

logger = get_logger(__name__)


class StepStatus(Enum):
    """Status of a pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStatus(Enum):
    """Status of the entire pipeline."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StepResult:
    """Result of executing a pipeline step."""

    status: StepStatus
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time: Optional[float] = None


@dataclass
class PipelineContext:
    """Context passed between pipeline steps."""

    file_id: str
    email: str
    original_filename: str
    file_path: Path
    metadata: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, StepResult] = field(default_factory=dict)


class PipelineStep(ABC):
    """Abstract base class for pipeline steps."""

    def __init__(self, name: str, description: str = "", retry_count: int = 0):
        self.name = name
        self.description = description
        self.retry_count = retry_count

    @abstractmethod
    async def execute(self, context: PipelineContext) -> StepResult:
        """Execute the pipeline step."""
        pass

    def should_skip(self, context: PipelineContext) -> bool:
        """Determine if this step should be skipped based on context."""
        return False

    def can_retry(self, attempt: int, error: Exception) -> bool:
        """Determine if this step can be retried after failure."""
        return attempt < self.retry_count


class Pipeline:
    """Pipeline orchestrator that executes steps in sequence."""

    def __init__(self, name: str, steps: Sequence[PipelineStep]):
        self.name = name
        self.steps = steps
        self.status = PipelineStatus.PENDING
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.current_step_index = 0

    async def execute(self, context: PipelineContext) -> Dict[str, Any]:
        """Execute the pipeline with the given context."""
        self.status = PipelineStatus.RUNNING
        self.start_time = datetime.now()

        logger.info(f"Starting pipeline '{self.name}' for {context.email}: {context.file_id}")

        try:
            for i, step in enumerate(self.steps):
                self.current_step_index = i

                if step.should_skip(context):
                    result = StepResult(
                        status=StepStatus.SKIPPED,
                        message=f"Step '{step.name}' was skipped",
                    )
                    context.step_results[step.name] = result
                    logger.info(f"Skipped step '{step.name}' for {context.file_id}")
                    continue

                # Execute step with retry logic
                result = await self._execute_step_with_retry(step, context)
                context.step_results[step.name] = result

                if result.status == StepStatus.FAILED:
                    self.status = PipelineStatus.FAILED
                    logger.error(
                        f"Pipeline '{self.name}' failed at step '{step.name}' " f"for {context.file_id}: {result.error}"
                    )
                    break

                logger.info(f"Completed step '{step.name}' for {context.file_id}: {result.message}")

            if self.status != PipelineStatus.FAILED:
                self.status = PipelineStatus.SUCCESS
                logger.info(f"Pipeline '{self.name}' completed successfully for {context.file_id}")

        except Exception as e:
            self.status = PipelineStatus.FAILED
            logger.error(f"Pipeline '{self.name}' failed with exception: {str(e)}")
            raise

        finally:
            self.end_time = datetime.now()

        return self._get_pipeline_summary(context)

    async def _execute_step_with_retry(self, step: PipelineStep, context: PipelineContext) -> StepResult:
        """Execute a step with retry logic."""
        attempt = 0
        last_error = None

        while attempt <= step.retry_count:
            try:
                start_time = datetime.now()
                logger.info(
                    f"Executing step '{step.name}' for {context.file_id} "
                    f"(attempt {attempt + 1}/{step.retry_count + 1})"
                )

                result = await step.execute(context)
                execution_time = (datetime.now() - start_time).total_seconds()
                result.execution_time = execution_time

                if result.status == StepStatus.SUCCESS:
                    return result
                elif result.status == StepStatus.FAILED:
                    last_error = Exception(result.error or "Step failed")
                    if not step.can_retry(attempt, last_error):
                        return result

            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                last_error = e

                if not step.can_retry(attempt, e):
                    return StepResult(
                        status=StepStatus.FAILED,
                        message=f"Step '{step.name}' failed after {attempt + 1} attempts",
                        error=str(e),
                        execution_time=execution_time,
                    )

                logger.warning(f"Step '{step.name}' failed (attempt {attempt + 1}): {str(e)}. " f"Retrying...")

            attempt += 1
            if attempt <= step.retry_count:
                # Exponential backoff
                await asyncio.sleep(2**attempt)

        # All retries exhausted
        return StepResult(
            status=StepStatus.FAILED,
            message=f"Step '{step.name}' failed after {attempt} attempts",
            error=str(last_error) if last_error else "Unknown error",
        )

    def _get_pipeline_summary(self, context: PipelineContext) -> Dict[str, Any]:
        """Get a summary of the pipeline execution."""
        total_time = None
        if self.start_time and self.end_time:
            total_time = (self.end_time - self.start_time).total_seconds()

        return {
            "pipeline_name": self.name,
            "status": self.status.value,
            "file_id": context.file_id,
            "email": context.email,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_execution_time": total_time,
            "steps_completed": len([r for r in context.step_results.values() if r.status == StepStatus.SUCCESS]),
            "steps_failed": len([r for r in context.step_results.values() if r.status == StepStatus.FAILED]),
            "step_results": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "execution_time": result.execution_time,
                    "error": result.error,
                }
                for name, result in context.step_results.items()
            },
        }


class PipelineRegistry:
    """Registry for managing different pipeline configurations."""

    def __init__(self) -> None:
        self._pipelines: Dict[str, Type[Pipeline]] = {}
        self._step_registry: Dict[str, Type[PipelineStep]] = {}

    def register_step(self, step_class: Type[PipelineStep]) -> None:
        """Register a pipeline step class."""
        self._step_registry[step_class.__name__] = step_class

    def register_pipeline(self, name: str, pipeline_class: Type[Pipeline]) -> None:
        """Register a pipeline class."""
        self._pipelines[name] = pipeline_class

    def create_pipeline(self, name: str, steps: List[PipelineStep]) -> Pipeline:
        """Create a pipeline instance."""
        return Pipeline(name, steps)

    def get_step_class(self, name: str) -> Type[PipelineStep]:
        """Get a registered step class by name."""
        if name not in self._step_registry:
            raise ValueError(f"Step '{name}' not registered")
        return self._step_registry[name]

    def list_available_steps(self) -> List[str]:
        """List all available step types."""
        return list(self._step_registry.keys())


# Global registry instance
pipeline_registry = PipelineRegistry()
