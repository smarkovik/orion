#!/usr/bin/env python3
"""
Parse E2E Integration Test Results for GitHub Actions

This script parses the test results JSON file and displays a formatted summary
of the integration test results, including infrastructure tests, SDK tests,
and performance metrics.

Usage:
    python parse_results.py

Expected Input:
    - integration-tests/last_test_report.json

Output:
    - Formatted test summary
    - Exit code 0 if all tests passed, 1 if any failed
"""

import json
import sys
from pathlib import Path


def parse_test_results():
    """Parse and display the integration test results."""
    
    results_file = Path("integration-tests/last_test_report.json")
    
    if not results_file.exists():
        print("ERROR: Test results file not found!")
        print(f"Expected: {results_file}")
        sys.exit(1)
    
    try:
        with open(results_file, "r") as f:
            results = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to parse test results: {e}")
        sys.exit(1)
    
    # Display infrastructure tests
    print("="*50)
    print("INFRASTRUCTURE TESTS")
    print("="*50)
    print(f"  Docker Build: {'PASS' if results.get('docker_build') else 'FAIL'}")
    print(f"  Docker Start: {'PASS' if results.get('docker_start') else 'FAIL'}")
    print(f"  API Health:   {'PASS' if results.get('api_health') else 'FAIL'}")
    
    # Display SDK tests
    print("\n" + "="*50)
    print("SDK TESTS")
    print("="*50)
    print(f"  Upload Files: {'PASS' if results.get('upload_files') else 'FAIL'}")
    print(f"  Processing:   {'PASS' if results.get('wait_processing') else 'FAIL'}")
    print(f"  Cosine Search: {'PASS' if results.get('cosine_search') else 'FAIL'}")
    print(f"  Hybrid Search: {'PASS' if results.get('hybrid_search') else 'FAIL'}")
    
    # Display file uploads details if available
    if "file_uploads" in results:
        uploads = results["file_uploads"]
        success_count = len([u for u in uploads if u.get("status") == "uploaded"])
        print(f"\nFile Upload Details:")
        print(f"  Total Files: {len(uploads)}")
        print(f"  Successful: {success_count}")
        print(f"  Failed: {len(uploads) - success_count}")
        
        for i, upload in enumerate(uploads, 1):
            status = upload.get("status", "unknown")
            filename = upload.get("filename", "unknown")
            print(f"    {i}. {filename}: {status.upper()}")
    
    # Display performance metrics
    print("\n" + "="*50)
    print("PERFORMANCE METRICS")
    print("="*50)
    
    if "upload_times" in results and results["upload_times"]:
        avg_upload = sum(results["upload_times"]) / len(results["upload_times"])
        max_upload = max(results["upload_times"])
        min_upload = min(results["upload_times"])
        print(f"  Upload Times:")
        print(f"    Average: {avg_upload:.2f}s")
        print(f"    Min: {min_upload:.2f}s")
        print(f"    Max: {max_upload:.2f}s")
    
    if "search_times" in results and results["search_times"]:
        avg_search = sum(results["search_times"]) / len(results["search_times"])
        max_search = max(results["search_times"])
        min_search = min(results["search_times"])
        print(f"  Search Times:")
        print(f"    Average: {avg_search:.3f}s")
        print(f"    Min: {min_search:.3f}s")
        print(f"    Max: {max_search:.3f}s")
    
    total_duration = results.get("total_duration", "N/A")
    print(f"  Total Test Duration: {total_duration}s")
    
    # Display search results details if available
    if "search_results" in results:
        search_results = results["search_results"]
        print(f"\nSearch Results Details:")
        
        for search_type, search_data in search_results.items():
            if isinstance(search_data, dict) and "results" in search_data:
                result_count = len(search_data["results"])
                print(f"  {search_type.title()} Search: {result_count} results")
                
                if result_count > 0:
                    top_score = search_data["results"][0].get("similarity_score", 0)
                    print(f"    Top Result Score: {top_score:.3f}")
    
    # Determine overall success
    critical_tests = [
        "docker_build",
        "docker_start", 
        "api_health",
        "upload_files",
        "wait_processing"
    ]
    
    search_tests = [
        "cosine_search",
        "hybrid_search"
    ]
    
    critical_passed = all(results.get(test, False) for test in critical_tests)
    search_passed = any(results.get(test, False) for test in search_tests)
    
    overall_success = critical_passed and search_passed
    
    # Display overall result
    print("\n" + "="*50)
    print("OVERALL RESULT")
    print("="*50)
    
    if overall_success:
        print("✅ PASS: ALL INTEGRATION TESTS SUCCESSFUL!")
        print("\nThe Orion system is working correctly:")
        print("  - Docker deployment successful")
        print("  - File upload and processing working")
        print("  - Search functionality operational")
        print("  - API endpoints responding properly")
    else:
        print("❌ FAIL: SOME INTEGRATION TESTS FAILED!")
        print("\nFailed components:")
        
        for test in critical_tests:
            if not results.get(test, False):
                print(f"  - {test.replace('_', ' ').title()}")
        
        if not search_passed:
            print("  - Search functionality (both cosine and hybrid failed)")
    
    print("\n" + "="*50)
    
    # Exit with appropriate code
    sys.exit(0 if overall_success else 1)


def main():
    """Main entry point."""
    try:
        parse_test_results()
    except KeyboardInterrupt:
        print("\nScript interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
