#!/usr/bin/env python3
"""
Error handling example for the Orion SDK.

This example demonstrates how to properly handle various types of errors
that can occur when using the SDK.
"""

import sys
from pathlib import Path

# Add the SDK to the path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from orion_sdk import (
    APIError,
    AuthenticationError,
    DocumentUploadError,
    NetworkError,
    NotFoundError,
    OrionClient,
    OrionSDKError,
    ProcessingTimeoutError,
    QueryError,
    RateLimitError,
    ValidationError,
)


def demonstrate_validation_errors():
    """Demonstrate validation error handling."""
    print("🔍 Testing validation errors...")

    client = OrionClient(base_url="http://localhost:8000")

    # Test invalid email
    print("\n1. Invalid email format:")
    try:
        response = client.search(query="test query", user_email="invalid-email", limit=10)  # Invalid email
    except ValidationError as e:
        print(f"   ✅ Caught ValidationError: {e}")
    except Exception as e:
        print(f"   ⚠️  Unexpected error: {e}")

    # Test empty query
    print("\n2. Empty query:")
    try:
        response = client.search(query="", user_email="test@example.com", limit=10)  # Empty query
    except ValidationError as e:
        print(f"   ✅ Caught ValidationError: {e}")
    except Exception as e:
        print(f"   ⚠️  Unexpected error: {e}")

    # Test invalid limit
    print("\n3. Invalid limit:")
    try:
        response = client.search(query="test query", user_email="test@example.com", limit=0)  # Invalid limit
    except ValidationError as e:
        print(f"   ✅ Caught ValidationError: {e}")
    except Exception as e:
        print(f"   ⚠️  Unexpected error: {e}")

    # Test non-existent file
    print("\n4. Non-existent file:")
    try:
        document = client.upload_document(
            file_path="non_existent_file.pdf", user_email="test@example.com"  # File doesn't exist
        )
    except ValidationError as e:
        print(f"   ✅ Caught ValidationError: {e}")
    except Exception as e:
        print(f"   ⚠️  Unexpected error: {e}")

    client.close()


def demonstrate_network_errors():
    """Demonstrate network error handling."""
    print("\n🌐 Testing network errors...")

    # Use an invalid URL to simulate network errors
    client = OrionClient(base_url="http://invalid-host:9999")

    print("\n1. Connection error (invalid host):")
    try:
        stats = client.get_library_stats("test@example.com")
    except NetworkError as e:
        print(f"   ✅ Caught NetworkError: {e}")
    except Exception as e:
        print(f"   ⚠️  Unexpected error type: {type(e).__name__}: {e}")

    client.close()


def demonstrate_api_errors():
    """Demonstrate API error handling."""
    print("\n🔌 Testing API errors...")

    # Use the real API but try operations that might fail
    client = OrionClient(base_url="http://localhost:8000")

    print("\n1. Searching non-existent user library:")
    try:
        response = client.search(query="test query", user_email="nonexistent@example.com", limit=10)
        print(f"   Results: {len(response.results)}")
    except APIError as e:
        print(f"   ✅ Caught APIError: {e}")
        print(f"      Status code: {e.status_code}")
    except QueryError as e:
        print(f"   ✅ Caught QueryError: {e}")
    except Exception as e:
        print(f"   ⚠️  Unexpected error: {type(e).__name__}: {e}")

    print("\n2. Invalid algorithm:")
    try:
        response = client.search(
            query="test query", user_email="test@example.com", algorithm="invalid_algorithm", limit=10
        )
    except ValidationError as e:
        print(f"   ✅ Caught ValidationError: {e}")
    except QueryError as e:
        print(f"   ✅ Caught QueryError: {e}")
    except Exception as e:
        print(f"   ⚠️  Unexpected error: {type(e).__name__}: {e}")

    client.close()


def demonstrate_timeout_handling():
    """Demonstrate timeout handling."""
    print("\n⏰ Testing timeout handling...")

    # Use a very short timeout to trigger timeout errors
    client = OrionClient(base_url="http://localhost:8000", timeout=0.001)  # 1ms timeout

    print("\n1. Very short timeout:")
    try:
        stats = client.get_library_stats("test@example.com")
    except NetworkError as e:
        print(f"   ✅ Caught NetworkError (likely timeout): {e}")
    except Exception as e:
        print(f"   ⚠️  Unexpected error: {type(e).__name__}: {e}")

    client.close()


def demonstrate_comprehensive_error_handling():
    """Demonstrate comprehensive error handling pattern."""
    print("\n🛡️  Comprehensive error handling example...")

    client = OrionClient(base_url="http://localhost:8000")

    def safe_operation(operation_name, operation_func):
        """Safely execute an operation with comprehensive error handling."""
        print(f"\n{operation_name}:")
        try:
            result = operation_func()
            print(f"   ✅ Success: {result}")
            return result
        except ValidationError as e:
            print(f"   ❌ Validation Error: {e}")
        except AuthenticationError as e:
            print(f"   ❌ Authentication Error: {e}")
        except NotFoundError as e:
            print(f"   ❌ Not Found Error: {e}")
        except RateLimitError as e:
            print(f"   ❌ Rate Limit Error: {e}")
        except DocumentUploadError as e:
            print(f"   ❌ Document Upload Error: {e}")
        except ProcessingTimeoutError as e:
            print(f"   ❌ Processing Timeout Error: {e}")
        except QueryError as e:
            print(f"   ❌ Query Error: {e}")
        except APIError as e:
            print(f"   ❌ API Error: {e} (Status: {e.status_code})")
        except NetworkError as e:
            print(f"   ❌ Network Error: {e}")
        except OrionSDKError as e:
            print(f"   ❌ SDK Error: {e}")
        except Exception as e:
            print(f"   ❌ Unexpected Error: {type(e).__name__}: {e}")
        return None

    # Test various operations
    safe_operation("Get library stats", lambda: client.get_library_stats("test@example.com"))

    safe_operation("Get supported algorithms", lambda: client.get_supported_algorithms())

    safe_operation("Search with valid params", lambda: client.search("test query", "test@example.com", limit=5))

    safe_operation("Search with invalid email", lambda: client.search("test query", "invalid-email", limit=5))

    client.close()


def main():
    """Main function to run all error handling examples."""
    print("This example demonstrates various error conditions and how to handle them.")
    print("Note: Some errors are expected and demonstrate proper error handling.\n")

    try:
        demonstrate_validation_errors()
        demonstrate_network_errors()
        demonstrate_api_errors()
        demonstrate_timeout_handling()
        demonstrate_comprehensive_error_handling()

    except Exception as e:
        print(f"\n❌ Unexpected error in main: {e}")
        import traceback

        traceback.print_exc()

    print("\n✅ Error handling demonstration completed")
    print("\nKey takeaways:")
    print("- Always catch specific exception types when possible")
    print("- ValidationError: Input validation failures")
    print("- NetworkError: Connection and network issues")
    print("- APIError: Server-side errors with status codes")
    print("- QueryError: Search-specific errors")
    print("- DocumentUploadError: Upload-specific errors")
    print("- OrionSDKError: Base class for all SDK errors")


if __name__ == "__main__":
    print("Orion SDK - Error Handling Example")
    print("=" * 40)
    main()
