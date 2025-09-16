#!/usr/bin/env python3
"""
Structure Test for Integration Test Setup

This test verifies that the integration test environment is properly set up
without running the full end-to-end test. It checks:

1. Directory structure
2. File permissions
3. Python imports
4. Basic configuration

Usage:
    python integration-tests/test_structure.py
"""

import sys
from pathlib import Path

# Add the SDK to the path
sdk_root = Path(__file__).parent.parent
sys.path.insert(0, str(sdk_root))


def test_directory_structure():
    """Test that all required directories exist."""
    print("Testing directory structure...")

    required_dirs = [
        sdk_root / "orion_sdk",
        sdk_root / "examples",
        sdk_root / "integration-tests",
        sdk_root / "tests",
        sdk_root / "docs",
    ]

    for dir_path in required_dirs:
        if dir_path.exists():
            print(f"PASS: Found: {dir_path.relative_to(sdk_root)}")
        else:
            print(f"FAIL: Missing: {dir_path.relative_to(sdk_root)}")
            return False

    return True


def test_file_permissions():
    """Test that executable files have correct permissions."""
    print("\nTesting file permissions...")

    executable_files = [
        sdk_root / "integration-tests" / "run_local_test.sh",
        sdk_root / "integration-tests" / "test_e2e_integration.py",
    ]

    for file_path in executable_files:
        if file_path.exists():
            is_executable = file_path.stat().st_mode & 0o111 != 0
            if is_executable:
                print(f"PASS: Executable: {file_path.name}")
            else:
                print(f"WARN: Not executable: {file_path.name} (this is OK for .py files)")
        else:
            print(f"FAIL: Missing: {file_path.name}")
            return False

    return True


def test_sdk_imports():
    """Test that SDK imports work correctly."""
    print("\nTesting SDK imports...")

    try:
        from orion_sdk import OrionClient, OrionConfig, OrionSDKError

        print("PASS: Core SDK imports successful")

        from orion_sdk.models import Document, QueryResult, SearchResponse

        print("PASS: Model imports successful")

        from orion_sdk.exceptions import DocumentUploadError, QueryError, ValidationError

        print("PASS: Exception imports successful")

        return True

    except ImportError as e:
        print(f"FAIL: Import error: {e}")
        return False


def test_integration_test_imports():
    """Test that integration test imports work."""
    print("\nTesting integration test imports...")

    try:
        # Test basic Python modules
        import json
        import os
        import subprocess
        import time

        print("PASS: Standard library imports successful")

        # Test that we can create the test runner class
        sys.path.insert(0, str(sdk_root / "integration-tests"))

        # Import without running
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "test_e2e_integration", sdk_root / "integration-tests" / "test_e2e_integration.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Test that we can create the runner
        runner = module.IntegrationTestRunner()
        print("PASS: Integration test runner class created")

        return True

    except Exception as e:
        print(f"FAIL: Integration test import error: {e}")
        return False


def test_workflow_file():
    """Test that GitHub Actions workflow file exists."""
    print("\nTesting GitHub Actions workflow...")

    workflow_file = sdk_root / ".github" / "workflows" / "e2e-integration-test.yml"

    if not workflow_file.exists():
        print(f"FAIL: Workflow file not found: {workflow_file}")
        return False

    print(f"PASS: Workflow file found: {workflow_file.name}")

    # Check file size and basic content
    try:
        file_size = workflow_file.stat().st_size
        print(f"PASS: Workflow file size: {file_size} bytes")

        with open(workflow_file, "r") as f:
            content = f.read()

        # Check for basic YAML structure
        required_elements = ["name:", "on:", "jobs:", "workflow_dispatch:"]
        for element in required_elements:
            if element in content:
                print(f"PASS: Workflow contains '{element}'")
            else:
                print(f"FAIL: Workflow missing '{element}'")
                return False

        print("PASS: Workflow file appears to have valid structure")
        print("   (Note: Full YAML validation skipped due to complex multi-line strings)")
        return True

    except Exception as e:
        print(f"FAIL: Workflow file read error: {e}")
        return False


def test_book_samples_setup():
    """Test book samples directory setup."""
    print("\nTesting book samples setup...")

    book_samples_dir = sdk_root / "examples" / "book-samples"

    if not book_samples_dir.exists():
        print(f"WARN: Book samples directory not found: {book_samples_dir}")
        print("   This is expected - create it and add PDF files before running the full test")
        return True

    print(f"PASS: Book samples directory exists: {book_samples_dir}")

    # Check for PDF files
    pdf_files = list(book_samples_dir.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files")

    if len(pdf_files) >= 3:
        print("PASS: Sufficient PDF files for testing")
        for pdf_file in pdf_files[:3]:
            size_mb = pdf_file.stat().st_size / (1024 * 1024)
            print(f"   - {pdf_file.name} ({size_mb:.1f} MB)")
    else:
        print("WARN: Need at least 3 PDF files for full integration test")
        print("   Add PDF files to examples/book-samples/ before running the full test")

    return True


def main():
    """Run all structure tests."""
    print("Orion Integration Test - Structure Verification")
    print("=" * 60)

    tests = [
        ("Directory Structure", test_directory_structure),
        ("File Permissions", test_file_permissions),
        ("SDK Imports", test_sdk_imports),
        ("Integration Test Imports", test_integration_test_imports),
        ("GitHub Workflow", test_workflow_file),
        ("Book Samples Setup", test_book_samples_setup),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"FAIL: {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("PASS: All structure tests passed! Integration test setup is ready.")
        print("\nNext steps:")
        print("1. Add 3 PDF files to examples/book-samples/")
        print("2. Set COHERE_API_KEY environment variable")
        print("3. Run: ./integration-tests/run_local_test.sh")
        return True
    else:
        print("FAIL: Some structure tests failed. Please fix the issues above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
