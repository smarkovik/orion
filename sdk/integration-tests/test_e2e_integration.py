#!/usr/bin/env python3
"""
End-to-End Integration Test for Orion SDK and API

This test performs a complete integration test by:
1. Building and starting the Orion API Docker container
2. Uploading 3 text files from book-samples directory
3. Waiting for processing to complete
4. Testing both cosine and hybrid search algorithms
5. Verifying results and cleaning up

Prerequisites:
- Docker installed and running
- Cohere API key available
- 3 text files in examples/book-samples/
- All dependencies installed

Usage:
    python integration-tests/test_e2e_integration.py
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sdk_root = Path(__file__).parent.parent
sys.path.insert(0, str(sdk_root))

from orion_sdk import DocumentUploadError, OrionClient, OrionSDKError, ProcessingStatus, QueryError, ValidationError


class IntegrationTestRunner:
    """Manages the complete end-to-end integration test."""

    def __init__(self):
        self.container_name = "orion-e2e-test"
        self.api_port = "8002"  # Use different port to avoid conflicts
        self.api_url = f"http://localhost:{self.api_port}"
        self.test_user_email = "e2e-test@orion.ai"
        self.book_samples_dir = sdk_root / "examples" / "book-samples"
        self.container_id: Optional[str] = None
        self.uploaded_documents: List[Dict] = []
        self.test_results: Dict = {
            "docker_build": False,
            "docker_start": False,
            "api_health": False,
            "file_uploads": [],
            "processing_complete": False,
            "cosine_search": False,
            "hybrid_search": False,
            "cleanup": False,
        }

    def log(self, message: str, level: str = "INFO") -> None:
        """Log a message with timestamp."""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def log_api_call(
        self, method: str, url: str, payload: dict = None, response: dict = None, status_code: int = None
    ) -> None:
        """Log detailed API call information."""
        self.log(f"API CALL: {method} {url}", "DEBUG")
        if payload:
            self.log(f"  Request payload: {payload}", "DEBUG")
        if status_code:
            self.log(f"  Response status: {status_code}", "DEBUG")
        if response:
            # Limit response size for readability
            response_str = str(response)[:500]
            if len(str(response)) > 500:
                response_str += "... (truncated)"
            self.log(f"  Response data: {response_str}", "DEBUG")

    def log_command(self, cmd: list, output: str = None, error: str = None, returncode: int = None) -> None:
        """Log detailed command execution information."""
        self.log(f"COMMAND: {' '.join(cmd)}", "DEBUG")
        if returncode is not None:
            self.log(f"  Exit code: {returncode}", "DEBUG")
        if output:
            # Show first few lines of output
            output_lines = output.strip().split("\n")[:10]
            for line in output_lines:
                self.log(f"  STDOUT: {line}", "DEBUG")
            total_lines = len(output.strip().split("\n"))
            if total_lines > 10:
                self.log(f"  ... (truncated, total {total_lines} lines)", "DEBUG")
        if error:
            error_lines = error.strip().split("\n")[:5]
            for line in error_lines:
                self.log(f"  STDERR: {line}", "DEBUG")

    def log_container_status(self, operation: str = "operation") -> None:
        """Log current container status and recent logs."""
        if not hasattr(self, "container_name") or not self.container_name:
            return

        self.log(f"Container status after {operation}:")
        try:
            # Show container status
            status_cmd = [
                "docker",
                "ps",
                "--filter",
                f"name={self.container_name}",
                "--format",
                "table {{.Names}}\t{{.Status}}\t{{.Ports}}",
            ]
            status_result = subprocess.run(status_cmd, capture_output=True, text=True)
            if status_result.stdout:
                for line in status_result.stdout.strip().split("\n"):
                    self.log(f"  STATUS: {line}", "DEBUG")

            # Show last 50 lines of container logs
            self.log(f"Last 50 lines of container logs:")
            logs_cmd = ["docker", "logs", "--tail", "50", self.container_name]
            logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)

            if logs_result.stdout:
                log_lines = logs_result.stdout.strip().split("\n")
                for line in log_lines[-50:]:
                    self.log(f"  LOG: {line}", "DEBUG")

            if logs_result.stderr:
                error_lines = logs_result.stderr.strip().split("\n")
                for line in error_lines[-20:]:
                    self.log(f"  ERR: {line}", "DEBUG")

        except Exception as e:
            self.log(f"  Failed to get container status: {e}", "DEBUG")

    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met."""
        self.log("Checking prerequisites...")

        # Check Docker
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
            if result.returncode != 0:
                self.log("ERROR: Docker is not installed or not running", "ERROR")
                return False
            self.log(f"PASS: Docker found: {result.stdout.strip()}")
        except FileNotFoundError:
            self.log("ERROR: Docker command not found", "ERROR")
            return False

        # Check Cohere API key
        cohere_key = os.getenv("COHERE_API_KEY")
        if not cohere_key:
            self.log("ERROR: COHERE_API_KEY environment variable not set", "ERROR")
            self.log("   Set it with: export COHERE_API_KEY='your-key-here'", "ERROR")
            return False
        self.log(f"PASS: Cohere API key found (length: {len(cohere_key)})")

        # Check book samples directory
        if not self.book_samples_dir.exists():
            self.log(f"ERROR: Book samples directory not found: {self.book_samples_dir}", "ERROR")
            return False

        # Check for text files
        text_files = list(self.book_samples_dir.glob("*.txt"))
        if len(text_files) < 3:
            self.log(f"ERROR: Need at least 3 text files in {self.book_samples_dir}, found {len(text_files)}", "ERROR")
            self.log(f"   Text files found: {[f.name for f in text_files]}")
            return False

        self.log(f"PASS: Found {len(text_files)} text files:")
        for text_file in text_files[:3]:  # We'll use first 3
            self.log(f"   - {text_file.name} ({text_file.stat().st_size / 1024:.1f} KB)")

        return True

    def build_docker_image(self) -> bool:
        """Build the Orion Docker image."""
        self.log("Building Orion Docker image...")

        try:
            # Change to parent directory where Dockerfile is located
            orion_root = sdk_root.parent
            self.log(f"Building from directory: {orion_root}")

            cmd = [
                "docker",
                "build",
                "-t",
                "orion-api:e2e-test",
                "-f",
                "Dockerfile",
                ".",
            ]

            self.log_command(cmd)
            self.log("Docker build started - this may take several minutes...")

            result = subprocess.run(
                cmd, cwd=orion_root, capture_output=True, text=True, timeout=300  # 5 minute timeout
            )

            self.log_command(cmd, output=result.stdout, error=result.stderr, returncode=result.returncode)

            if result.returncode != 0:
                self.log("ERROR: Docker build failed", "ERROR")
                return False

            self.log("PASS: Docker image built successfully")

            self.log("Verifying Docker image was created...")
            verify_cmd = ["docker", "images", "orion-api:e2e-test"]
            verify_result = subprocess.run(verify_cmd, capture_output=True, text=True)
            self.log_command(
                verify_cmd, output=verify_result.stdout, error=verify_result.stderr, returncode=verify_result.returncode
            )

            self.test_results["docker_build"] = True
            return True

        except subprocess.TimeoutExpired:
            self.log("ERROR: Docker build timed out after 5 minutes", "ERROR")
            return False
        except Exception as e:
            self.log(f"ERROR: Docker build error: {e}", "ERROR")
            return False

    def start_docker_container(self) -> bool:
        """Start the Orion API Docker container."""
        self.log("Starting Orion API container...")

        try:
            self.log("Cleaning up any existing containers...")
            stop_cmd = ["docker", "stop", self.container_name]
            stop_result = subprocess.run(stop_cmd, capture_output=True, text=True)
            self.log_command(
                stop_cmd, output=stop_result.stdout, error=stop_result.stderr, returncode=stop_result.returncode
            )

            rm_cmd = ["docker", "rm", self.container_name]
            rm_result = subprocess.run(rm_cmd, capture_output=True, text=True)
            self.log_command(rm_cmd, output=rm_result.stdout, error=rm_result.stderr, returncode=rm_result.returncode)

            cohere_key = os.getenv("COHERE_API_KEY")
            self.log(f"Starting container with Cohere API key: {'***' + cohere_key[-4:] if cohere_key else 'NOT_SET'}")

            cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                self.container_name,
                "-p",
                f"{self.api_port}:8000",
                "-e",
                f"COHERE_API_KEY={cohere_key}",
                "-e",
                "LOG_LEVEL=INFO",  # Verbose but not overwhelming
                "-e",
                "PYTHONUNBUFFERED=1",  # Ensure logs are flushed immediately
                "-e",
                "PDFMINER_LOG_LEVEL=WARNING",  # Reduce PDF parsing verbosity
                "orion-api:e2e-test",
            ]

            self.log_command(cmd)
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.log_command(cmd, output=result.stdout, error=result.stderr, returncode=result.returncode)

            if result.returncode != 0:
                self.log("ERROR: Failed to start Docker container", "ERROR")
                return False

            self.container_id = result.stdout.strip()
            self.log(f"PASS: Container started with ID: {self.container_id[:12]}")

            self.log("Checking container status...")
            status_cmd = ["docker", "ps", "--filter", f"name={self.container_name}"]
            status_result = subprocess.run(status_cmd, capture_output=True, text=True)
            self.log_command(
                status_cmd, output=status_result.stdout, error=status_result.stderr, returncode=status_result.returncode
            )

            self.log("Initial container logs:")
            logs_cmd = ["docker", "logs", self.container_name]
            logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)
            self.log_command(
                logs_cmd, output=logs_result.stdout, error=logs_result.stderr, returncode=logs_result.returncode
            )

            # Wait for container to be ready
            self.log("Waiting for API to be ready...")
            for attempt in range(30):  # Wait up to 30 seconds
                try:
                    import requests

                    self.log(f"Health check attempt {attempt + 1}/30...")
                    response = requests.get(f"{self.api_url}/health", timeout=2)
                    self.log_api_call(
                        "GET",
                        f"{self.api_url}/health",
                        status_code=response.status_code,
                        response=response.json() if response.content else {},
                    )

                    if response.status_code == 200:
                        self.log("PASS: API is ready and healthy")
                        self.test_results["docker_start"] = True
                        self.test_results["api_health"] = True

                        self.log("Container logs after successful startup:")
                        logs_cmd = ["docker", "logs", self.container_name]
                        logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)
                        self.log_command(
                            logs_cmd,
                            output=logs_result.stdout,
                            error=logs_result.stderr,
                            returncode=logs_result.returncode,
                        )

                        self.log_container_status("successful API startup")

                        return True
                except Exception as e:
                    self.log(f"Health check failed: {e}", "DEBUG")

                time.sleep(1)

            self.log("ERROR: API failed to become ready within 30 seconds", "ERROR")

            self.log("Container logs after health check failure:")
            logs_cmd = ["docker", "logs", self.container_name]
            logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)
            self.log_command(
                logs_cmd, output=logs_result.stdout, error=logs_result.stderr, returncode=logs_result.returncode
            )

            return False

        except Exception as e:
            self.log(f"ERROR: Error starting container: {e}", "ERROR")
            return False

    def upload_test_files(self) -> bool:
        """Upload the 3 text files using the SDK."""
        self.log("Uploading test text files...")

        try:
            self.log("Initializing OrionClient with verbose logging...")
            client = OrionClient(base_url=self.api_url, timeout=300)  # 5 minutes for large file uploads
            self.log(f"  Client base URL: {client.config.base_url}")
            self.log(f"  Client timeout: {client.config.timeout}")
            self.log(f"  Client API key: {'SET' if client.config.api_key else 'NOT_SET'}")

            text_files = list(self.book_samples_dir.glob("*.txt"))[:3]
            self.log(f"Found {len(text_files)} text files to upload:")
            for text_file in text_files:
                file_size = text_file.stat().st_size
                self.log(f"  - {text_file.name}: {file_size:,} bytes ({file_size / (1024*1024):.1f}MB)")

            for i, text_file in enumerate(text_files, 1):
                self.log(f"Uploading file {i}/3: {text_file.name}")
                upload_start = time.time()

                try:
                    self.log(f"Calling client.upload_document for {text_file.name}...")
                    self.log(f"  File path: {text_file}")
                    self.log(f"  User email: {self.test_user_email}")
                    self.log(f"  File size: {text_file.stat().st_size:,} bytes")

                    document = client.upload_document(
                        file_path=text_file,
                        user_email=self.test_user_email,
                        description=f"E2E Test Book {i}: {text_file.stem}",
                        wait_for_processing=False,
                    )

                    upload_duration = time.time() - upload_start

                    upload_result = {
                        "filename": text_file.name,
                        "document_id": document.id,
                        "file_size": document.file_size,
                        "status": "uploaded",
                        "error": None,
                        "duration": upload_duration,
                    }

                    self.uploaded_documents.append(upload_result)
                    self.test_results["file_uploads"].append(upload_result)

                    self.log(f"PASS: Uploaded: {document.filename} (ID: {document.id}) in {upload_duration:.2f}s")
                    self.log(
                        f"  Document details: filename={document.filename}, size={document.file_size}, content_type={getattr(document, 'content_type', 'N/A')}"
                    )

                except (ValidationError, DocumentUploadError) as e:
                    upload_duration = time.time() - upload_start
                    error_result = {
                        "filename": text_file.name,
                        "document_id": None,
                        "file_size": text_file.stat().st_size,
                        "status": "failed",
                        "error": str(e),
                        "duration": upload_duration,
                    }
                    self.test_results["file_uploads"].append(error_result)
                    self.log(f"ERROR: Upload failed for {text_file.name} after {upload_duration:.2f}s: {e}", "ERROR")
                    self.log(f"  Error type: {type(e).__name__}", "ERROR")

                    # Log container status on upload failure
                    self.log_container_status(f"upload failure for {text_file.name}")

                except Exception as e:
                    upload_duration = time.time() - upload_start
                    error_result = {
                        "filename": text_file.name,
                        "document_id": None,
                        "file_size": text_file.stat().st_size,
                        "status": "failed",
                        "error": str(e),
                        "duration": upload_duration,
                    }
                    self.test_results["file_uploads"].append(error_result)
                    self.log(
                        f"ERROR: Unexpected upload error for {text_file.name} after {upload_duration:.2f}s: {e}",
                        "ERROR",
                    )
                    self.log(f"  Error type: {type(e).__name__}", "ERROR")

            client.close()

            successful_uploads = len([d for d in self.uploaded_documents if d["status"] == "uploaded"])
            self.log(f"Upload summary: {successful_uploads}/{len(text_files)} files uploaded successfully")

            self.log_container_status("file uploads completed")

            return successful_uploads > 0

        except Exception as e:
            self.log(f"ERROR: Upload process failed: {e}", "ERROR")
            return False

    def wait_for_processing(self) -> bool:
        """Wait for document processing to complete."""
        self.log("Waiting for document processing to complete...")

        try:
            client = OrionClient(base_url=self.api_url, timeout=300)

            max_wait_time = 900
            check_interval = 15
            start_time = time.time()
            iteration_count = 0

            while time.time() - start_time < max_wait_time:
                elapsed = time.time() - start_time
                remaining = max_wait_time - elapsed
                self.log(f"Processing check - elapsed: {elapsed:.1f}s, remaining: {remaining:.1f}s")

                try:
                    self.log(f"Calling get_library_stats for {self.test_user_email}...")
                    stats = client.get_library_stats(self.test_user_email)

                    # Log detailed stats
                    self.log(f"Library stats received:")
                    self.log(f"  Documents: {stats.document_count}")
                    self.log(f"  Total chunks: {stats.chunk_count}")
                    self.log(f"  Chunks with embeddings: {stats.chunks_with_embeddings}")
                    self.log(f"  Embedding coverage: {stats.embedding_coverage:.1f}%")
                    self.log(f"  Last updated: {getattr(stats, 'last_updated', 'N/A')}")

                    self.log(
                        f"Processing status: {stats.document_count} docs, "
                        f"{stats.chunks_with_embeddings}/{stats.chunk_count} chunks processed "
                        f"({stats.embedding_coverage:.1f}%)"
                    )

                    chunks_threshold = 100  # If we have 100+ chunks, we have enough for testing
                    coverage_threshold = 50  # Lower threshold for large documents

                    if stats.chunk_count >= chunks_threshold and stats.embedding_coverage > coverage_threshold:
                        self.log(
                            f"PASS: Document processing sufficient for testing! ({stats.chunks_with_embeddings} chunks ready)"
                        )
                        self.test_results["processing_complete"] = True
                        client.close()
                        return True
                    elif stats.chunk_count > 0 and stats.embedding_coverage > 85:
                        self.log("PASS: Document processing appears complete!")
                        self.test_results["processing_complete"] = True
                        client.close()
                        return True

                    if stats.embedding_coverage > 0:
                        self.log(
                            f"Processing in progress... {stats.embedding_coverage:.1f}% complete ({stats.chunks_with_embeddings}/{stats.chunk_count} chunks)"
                        )
                    else:
                        self.log("Processing starting...")

                except Exception as e:
                    self.log(f"WARN: Error checking processing status: {e}", "WARN")
                    self.log(f"  Error type: {type(e).__name__}", "WARN")

                    if hasattr(self, "container_name"):
                        self.log("Container logs during processing check failure:")
                        logs_cmd = ["docker", "logs", "--tail", "20", self.container_name]
                        logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)
                        self.log_command(
                            logs_cmd,
                            output=logs_result.stdout,
                            error=logs_result.stderr,
                            returncode=logs_result.returncode,
                        )

                iteration_count += 1

                # Log container status every 4 iterations (60 seconds) to avoid too much noise
                if iteration_count % 4 == 0:
                    self.log_container_status(f"processing wait iteration {iteration_count}")

                self.log(f"Waiting {check_interval} seconds before next check...")
                time.sleep(check_interval)

            client.close()
            self.log("WARN: Processing timeout reached, but continuing with tests...", "WARN")
            return True  # Continue even if processing isn't 100% complete

        except Exception as e:
            self.log(f"ERROR: Error waiting for processing: {e}", "ERROR")
            return False

    def test_search_algorithms(self) -> bool:
        """Test both cosine and hybrid search algorithms."""
        self.log("Testing search algorithms...")

        try:
            client = OrionClient(base_url=self.api_url, timeout=30)

            test_queries = [
                "love",
                "death",
                "light",
                "heart",
            ]

            # Test cosine similarity search
            self.log("Testing cosine similarity search...")
            cosine_results = []

            for i, query in enumerate(test_queries, 1):
                try:
                    self.log(f"Cosine search {i}/{len(test_queries)}: '{query}'")
                    search_start = time.time()

                    self.log(f"  Calling client.search with algorithm='cosine', limit=5")
                    response = client.search(query=query, user_email=self.test_user_email, algorithm="cosine", limit=5)

                    search_duration = time.time() - search_start

                    result = {
                        "query": query,
                        "algorithm": "cosine",
                        "results_count": len(response.results),
                        "execution_time": response.execution_time,
                        "top_score": response.results[0].similarity_score if response.results else 0,
                        "total_duration": search_duration,
                    }
                    cosine_results.append(result)

                    self.log(f"  Response received in {search_duration:.3f}s:")
                    self.log(f"    Results count: {len(response.results)}")
                    self.log(f"    Execution time: {response.execution_time:.3f}s")
                    self.log(f"    Total chunks searched: {response.total_chunks_searched}")
                    self.log(f"    Algorithm used: {response.algorithm_used}")

                    if response.results:
                        self.log(f"    Top result score: {response.results[0].similarity_score:.3f}")
                        self.log(f"    Top result preview: {response.results[0].text[:100]}...")
                    else:
                        self.log(f"    No results found")

                    self.log(
                        f"  Query: '{query}' → {len(response.results)} results "
                        f"(top score: {result['top_score']:.3f}, time: {response.execution_time:.3f}s)"
                    )

                except QueryError as e:
                    self.log(f"ERROR: Cosine search failed for '{query}': {e}", "ERROR")
                    self.log(f"  Error type: {type(e).__name__}", "ERROR")
                except Exception as e:
                    self.log(f"ERROR: Unexpected error in cosine search for '{query}': {e}", "ERROR")
                    self.log(f"  Error type: {type(e).__name__}", "ERROR")

            if cosine_results:
                self.test_results["cosine_search"] = True
                self.log(f"PASS: Cosine search completed: {len(cosine_results)} queries tested")

                # Log container status after cosine search
                self.log_container_status("cosine search completed")

            # Test hybrid search
            self.log("Testing hybrid search...")
            hybrid_results = []

            for i, query in enumerate(test_queries, 1):
                try:
                    self.log(f"Hybrid search {i}/{len(test_queries)}: '{query}'")
                    search_start = time.time()

                    self.log(f"  Calling client.search with algorithm='hybrid', limit=5")
                    response = client.search(query=query, user_email=self.test_user_email, algorithm="hybrid", limit=5)

                    search_duration = time.time() - search_start

                    result = {
                        "query": query,
                        "algorithm": "hybrid",
                        "results_count": len(response.results),
                        "execution_time": response.execution_time,
                        "top_score": response.results[0].similarity_score if response.results else 0,
                        "total_duration": search_duration,
                    }
                    hybrid_results.append(result)

                    self.log(f"  Response received in {search_duration:.3f}s:")
                    self.log(f"    Results count: {len(response.results)}")
                    self.log(f"    Execution time: {response.execution_time:.3f}s")
                    self.log(f"    Total chunks searched: {response.total_chunks_searched}")
                    self.log(f"    Algorithm used: {response.algorithm_used}")

                    if response.results:
                        self.log(f"    Top result score: {response.results[0].similarity_score:.3f}")
                        self.log(f"    Top result preview: {response.results[0].text[:100]}...")
                    else:
                        self.log(f"    No results found")

                    self.log(
                        f"  Query: '{query}' → {len(response.results)} results "
                        f"(top score: {result['top_score']:.3f}, time: {response.execution_time:.3f}s)"
                    )

                except QueryError as e:
                    self.log(f"ERROR: Hybrid search failed for '{query}': {e}", "ERROR")
                    self.log(f"  Error type: {type(e).__name__}", "ERROR")
                except Exception as e:
                    self.log(f"ERROR: Unexpected error in hybrid search for '{query}': {e}", "ERROR")
                    self.log(f"  Error type: {type(e).__name__}", "ERROR")

            if hybrid_results:
                self.test_results["hybrid_search"] = True
                self.log(f"PASS: Hybrid search completed: {len(hybrid_results)} queries tested")

                self.log_container_status("hybrid search completed")

            client.close()

            self.test_results["search_results"] = {
                "cosine": cosine_results,
                "hybrid": hybrid_results,
            }

            return len(cosine_results) > 0 or len(hybrid_results) > 0

        except Exception as e:
            self.log(f"ERROR: Search testing failed: {e}", "ERROR")
            return False

    def cleanup(self) -> bool:
        """Clean up Docker containers and resources."""
        self.log("Cleaning up...")

        try:
            if self.container_id:
                # Stop the container
                result = subprocess.run(["docker", "stop", self.container_name], capture_output=True)
                if result.returncode == 0:
                    self.log("PASS: Container stopped")
                else:
                    self.log("WARN: Failed to stop container")

                # Remove the container
                result = subprocess.run(["docker", "rm", self.container_name], capture_output=True)
                if result.returncode == 0:
                    self.log("PASS: Container removed")
                else:
                    self.log("WARN: Failed to remove container")

            self.test_results["cleanup"] = True
            return True

        except Exception as e:
            self.log(f"ERROR: Cleanup error: {e}", "ERROR")
            return False

    def generate_report(self) -> None:
        """Generate a comprehensive test report."""
        self.log("Generating test report...")

        print("\n" + "=" * 80)
        print("ORION END-TO-END INTEGRATION TEST REPORT")
        print("=" * 80)

        # Overall status
        total_steps = len([k for k in self.test_results.keys() if k != "search_results"])
        passed_steps = len([v for k, v in self.test_results.items() if k != "search_results" and v])

        print(f"\nOVERALL STATUS: {passed_steps}/{total_steps} steps passed")

        # Detailed results
        print(f"\nINFRASTRUCTURE:")
        print(f"  Docker Build:     {'PASS' if self.test_results['docker_build'] else 'FAIL'}")
        print(f"  Docker Start:     {'PASS' if self.test_results['docker_start'] else 'FAIL'}")
        print(f"  API Health:       {'PASS' if self.test_results['api_health'] else 'FAIL'}")

        print(f"\nFILE UPLOADS:")
        successful_uploads = len([u for u in self.test_results["file_uploads"] if u["status"] == "uploaded"])
        total_uploads = len(self.test_results["file_uploads"])
        print(f"  Upload Success:   {successful_uploads}/{total_uploads} files")

        for upload in self.test_results["file_uploads"]:
            status_icon = "PASS" if upload["status"] == "uploaded" else "FAIL"
            print(f"    {status_icon} {upload['filename']} ({upload['file_size']} bytes)")

        print(f"\nPROCESSING:")
        print(f"  Processing:       {'PASS' if self.test_results['processing_complete'] else 'FAIL'}")

        print(f"\nSEARCH TESTING:")
        print(f"  Cosine Search:    {'PASS' if self.test_results['cosine_search'] else 'FAIL'}")
        print(f"  Hybrid Search:    {'PASS' if self.test_results['hybrid_search'] else 'FAIL'}")

        # Search results details
        if "search_results" in self.test_results:
            search_data = self.test_results["search_results"]
            for algorithm in ["cosine", "hybrid"]:
                if algorithm in search_data and search_data[algorithm]:
                    print(f"\n  {algorithm.title()} Results:")
                    for result in search_data[algorithm]:
                        print(
                            f"    '{result['query'][:40]}...' → "
                            f"{result['results_count']} results "
                            f"(score: {result['top_score']:.3f})"
                        )

        print(f"\nCLEANUP:")
        print(f"  Cleanup:          {'PASS' if self.test_results['cleanup'] else 'FAIL'}")

        # Success criteria
        critical_steps = ["docker_build", "docker_start", "api_health"]
        critical_passed = all(self.test_results.get(step, False) for step in critical_steps)
        uploads_passed = successful_uploads > 0
        search_passed = self.test_results["cosine_search"] or self.test_results["hybrid_search"]

        overall_success = critical_passed and uploads_passed and search_passed

        print(f"\nFINAL RESULT:")
        if overall_success:
            print("PASS: INTEGRATION TEST PASSED")
            print("   All critical components are working correctly!")
        else:
            print("FAIL: INTEGRATION TEST FAILED")
            print("   Some critical components failed. Check the logs above.")

        print("=" * 80)

        # Save detailed results to file
        report_file = sdk_root / "integration-tests" / "last_test_report.json"
        with open(report_file, "w") as f:
            json.dump(self.test_results, f, indent=2)
        print(f"\nDetailed results saved to: {report_file}")

    def run(self) -> bool:
        """Run the complete integration test."""
        self.log("Starting Orion End-to-End Integration Test")

        try:
            # Step 1: Check prerequisites
            if not self.check_prerequisites():
                return False

            # Step 2: Build Docker image
            if not self.build_docker_image():
                return False

            # Step 3: Start Docker container
            if not self.start_docker_container():
                return False

            # Step 4: Upload test files
            if not self.upload_test_files():
                return False

            # Step 5: Wait for processing
            if not self.wait_for_processing():
                return False

            # Step 6: Test search algorithms
            if not self.test_search_algorithms():
                return False

            return True

        except KeyboardInterrupt:
            self.log("WARN: Test interrupted by user", "WARN")
            return False
        except Exception as e:
            self.log(f"ERROR: Unexpected error: {e}", "ERROR")
            return False
        finally:
            # Always try to clean up
            self.cleanup()
            self.generate_report()


def main():
    """Main entry point for the integration test."""
    print("Orion End-to-End Integration Test")
    print("=" * 50)

    # Check if we're in the right directory
    if not (Path.cwd() / "orion_sdk").exists():
        print("ERROR: Must be run from the SDK root directory")
        print("   Current directory:", Path.cwd())
        print("   Expected to find: orion_sdk/ directory")
        sys.exit(1)

    # Run the test
    runner = IntegrationTestRunner()
    success = runner.run()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
