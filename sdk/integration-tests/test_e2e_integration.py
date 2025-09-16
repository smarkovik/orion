#!/usr/bin/env python3
"""
End-to-End Integration Test for Orion SDK and API

This test performs a complete integration test by:
1. Building and starting the Orion API Docker container
2. Uploading 3 PDF files from book-samples directory
3. Waiting for processing to complete
4. Testing both cosine and hybrid search algorithms
5. Verifying results and cleaning up

Prerequisites:
- Docker installed and running
- Cohere API key available
- 3 PDF files in examples/book-samples/
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

# Add the SDK to the path
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

        # Check for PDF files
        pdf_files = list(self.book_samples_dir.glob("*.pdf"))
        if len(pdf_files) < 3:
            self.log(f"ERROR: Need at least 3 PDF files in {self.book_samples_dir}, found {len(pdf_files)}", "ERROR")
            self.log(f"   PDF files found: {[f.name for f in pdf_files]}")
            return False

        self.log(f"PASS: Found {len(pdf_files)} PDF files:")
        for pdf_file in pdf_files[:3]:  # We'll use first 3
            self.log(f"   - {pdf_file.name} ({pdf_file.stat().st_size / 1024:.1f} KB)")

        return True

    def build_docker_image(self) -> bool:
        """Build the Orion Docker image."""
        self.log("Building Orion Docker image...")

        try:
            # Change to parent directory where Dockerfile is located
            orion_root = sdk_root.parent
            self.log(f"Building from directory: {orion_root}")

            # Build the Docker image
            cmd = [
                "docker",
                "build",
                "-t",
                "orion-api:e2e-test",
                "-f",
                "Dockerfile",
                ".",
            ]

            result = subprocess.run(
                cmd, cwd=orion_root, capture_output=True, text=True, timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                self.log("ERROR: Docker build failed", "ERROR")
                self.log(f"STDOUT: {result.stdout}", "ERROR")
                self.log(f"STDERR: {result.stderr}", "ERROR")
                return False

            self.log("PASS: Docker image built successfully")
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
            # Stop any existing container with the same name
            subprocess.run(["docker", "stop", self.container_name], capture_output=True)
            subprocess.run(["docker", "rm", self.container_name], capture_output=True)

            # Start the container
            cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                self.container_name,
                "-p",
                f"{self.api_port}:8000",
                "-e",
                f"COHERE_API_KEY={os.getenv('COHERE_API_KEY')}",
                "-e",
                "LOG_LEVEL=INFO",
                "orion-api:e2e-test",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                self.log("ERROR: Failed to start Docker container", "ERROR")
                self.log(f"STDERR: {result.stderr}", "ERROR")
                return False

            self.container_id = result.stdout.strip()
            self.log(f"PASS: Container started with ID: {self.container_id[:12]}")

            # Wait for container to be ready
            self.log("Waiting for API to be ready...")
            for attempt in range(30):  # Wait up to 30 seconds
                try:
                    import requests

                    response = requests.get(f"{self.api_url}/health", timeout=2)
                    if response.status_code == 200:
                        self.log("PASS: API is ready and healthy")
                        self.test_results["docker_start"] = True
                        self.test_results["api_health"] = True
                        return True
                except Exception:
                    pass

                time.sleep(1)

            self.log("ERROR: API failed to become ready within 30 seconds", "ERROR")
            return False

        except Exception as e:
            self.log(f"ERROR: Error starting container: {e}", "ERROR")
            return False

    def upload_test_files(self) -> bool:
        """Upload the 3 PDF files using the SDK."""
        self.log("Uploading test PDF files...")

        try:
            client = OrionClient(base_url=self.api_url, timeout=60)

            # Get first 3 PDF files
            pdf_files = list(self.book_samples_dir.glob("*.pdf"))[:3]

            for i, pdf_file in enumerate(pdf_files, 1):
                self.log(f"Uploading file {i}/3: {pdf_file.name}")

                try:
                    document = client.upload_document(
                        file_path=pdf_file,
                        user_email=self.test_user_email,
                        description=f"E2E Test Book {i}: {pdf_file.stem}",
                        wait_for_processing=False,
                    )

                    upload_result = {
                        "filename": pdf_file.name,
                        "document_id": document.id,
                        "file_size": document.file_size,
                        "status": "uploaded",
                        "error": None,
                    }

                    self.uploaded_documents.append(upload_result)
                    self.test_results["file_uploads"].append(upload_result)

                    self.log(f"PASS: Uploaded: {document.filename} (ID: {document.id})")

                except (ValidationError, DocumentUploadError) as e:
                    error_result = {
                        "filename": pdf_file.name,
                        "document_id": None,
                        "file_size": pdf_file.stat().st_size,
                        "status": "failed",
                        "error": str(e),
                    }
                    self.test_results["file_uploads"].append(error_result)
                    self.log(f"ERROR: Upload failed for {pdf_file.name}: {e}", "ERROR")

            client.close()

            successful_uploads = len([d for d in self.uploaded_documents if d["status"] == "uploaded"])
            self.log(f"Upload summary: {successful_uploads}/{len(pdf_files)} files uploaded successfully")

            return successful_uploads > 0

        except Exception as e:
            self.log(f"ERROR: Upload process failed: {e}", "ERROR")
            return False

    def wait_for_processing(self) -> bool:
        """Wait for document processing to complete."""
        self.log("Waiting for document processing to complete...")

        try:
            client = OrionClient(base_url=self.api_url, timeout=30)

            max_wait_time = 300  # 5 minutes
            check_interval = 10  # Check every 10 seconds
            start_time = time.time()

            while time.time() - start_time < max_wait_time:
                try:
                    stats = client.get_library_stats(self.test_user_email)

                    self.log(
                        f"Processing status: {stats.document_count} docs, "
                        f"{stats.chunks_with_embeddings}/{stats.chunk_count} chunks processed "
                        f"({stats.embedding_coverage:.1f}%)"
                    )

                    # Consider processing complete when we have good coverage
                    if stats.chunk_count > 0 and stats.embedding_coverage > 85:
                        self.log("PASS: Document processing appears complete!")
                        self.test_results["processing_complete"] = True
                        client.close()
                        return True

                    if stats.embedding_coverage > 0:
                        self.log(f"Processing in progress... {stats.embedding_coverage:.1f}% complete")
                    else:
                        self.log("Processing starting...")

                except Exception as e:
                    self.log(f"WARN: Error checking processing status: {e}")

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

            # Define test queries that should find relevant content
            test_queries = [
                "artificial intelligence and machine learning",
                "neural networks and deep learning",
                "natural language processing techniques",
                "computer vision applications",
            ]

            # Test cosine similarity search
            self.log("Testing cosine similarity search...")
            cosine_results = []

            for query in test_queries:
                try:
                    response = client.search(query=query, user_email=self.test_user_email, algorithm="cosine", limit=5)

                    result = {
                        "query": query,
                        "algorithm": "cosine",
                        "results_count": len(response.results),
                        "execution_time": response.execution_time,
                        "top_score": response.results[0].similarity_score if response.results else 0,
                    }
                    cosine_results.append(result)

                    self.log(
                        f"  Query: '{query}' → {len(response.results)} results "
                        f"(top score: {result['top_score']:.3f}, time: {response.execution_time:.3f}s)"
                    )

                except QueryError as e:
                    self.log(f"ERROR: Cosine search failed for '{query}': {e}", "ERROR")

            if cosine_results:
                self.test_results["cosine_search"] = True
                self.log(f"PASS: Cosine search completed: {len(cosine_results)} queries tested")

            # Test hybrid search
            self.log("Testing hybrid search...")
            hybrid_results = []

            for query in test_queries:
                try:
                    response = client.search(query=query, user_email=self.test_user_email, algorithm="hybrid", limit=5)

                    result = {
                        "query": query,
                        "algorithm": "hybrid",
                        "results_count": len(response.results),
                        "execution_time": response.execution_time,
                        "top_score": response.results[0].similarity_score if response.results else 0,
                    }
                    hybrid_results.append(result)

                    self.log(
                        f"  Query: '{query}' → {len(response.results)} results "
                        f"(top score: {result['top_score']:.3f}, time: {response.execution_time:.3f}s)"
                    )

                except QueryError as e:
                    self.log(f"ERROR: Hybrid search failed for '{query}': {e}", "ERROR")

            if hybrid_results:
                self.test_results["hybrid_search"] = True
                self.log(f"PASS: Hybrid search completed: {len(hybrid_results)} queries tested")

            client.close()

            # Store detailed results
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
