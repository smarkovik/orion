#!/usr/bin/env python3
"""
Basic usage example for the Orion SDK.

This example demonstrates the fundamental operations:
- Uploading a document
- Searching for content
- Getting library statistics
"""

import sys
import time
from pathlib import Path

# Add the SDK to the path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from orion_sdk import OrionClient, OrionSDKError


def main():
    """Main example function."""
    # Initialize the client
    print("🚀 Initializing Orion client...")
    client = OrionClient(base_url="http://localhost:8000", timeout=30)

    user_email = "demo@example.com"

    try:
        # Example 1: Get library statistics (before uploading)
        print("\n📊 Getting initial library statistics...")
        stats = client.get_library_stats(user_email)
        print(f"Library exists: {stats.exists}")
        print(f"Documents: {stats.document_count}")
        print(f"Chunks: {stats.chunk_count}")
        print(f"Total size: {stats.total_file_size_mb:.1f}MB")

        # Example 2: Get supported algorithms
        print("\n🔍 Getting supported search algorithms...")
        try:
            algorithms = client.get_supported_algorithms()
            print(f"Available algorithms: {', '.join(algorithms)}")
        except Exception as e:
            print(f"Note: Could not get algorithms (API might be down): {e}")
            algorithms = ["cosine"]  # Default fallback

        # Example 3: Check if we have documents to search
        if stats.exists and stats.document_count > 0:
            print(f"\n🔎 Searching existing library with {stats.document_count} documents...")

            # Perform a search
            search_queries = ["machine learning algorithms", "data processing", "important information", "key findings"]

            for query in search_queries:
                print(f"\nSearching for: '{query}'")
                try:
                    response = client.search(
                        query=query,
                        user_email=user_email,
                        algorithm=algorithms[0],  # Use first available algorithm
                        limit=3,
                    )

                    print(f"Found {len(response.results)} results in {response.execution_time:.3f}s")
                    print(
                        f"Searched {response.total_chunks_searched} chunks from {response.total_documents_searched} documents"
                    )

                    for i, result in enumerate(response.results[:2], 1):  # Show top 2 results
                        print(f"  {i}. Score: {result.similarity_score:.3f}")
                        print(f"     File: {result.original_filename}")
                        print(f"     Text: {result.text[:100]}...")
                        print()

                    if len(response.results) == 0:
                        print("  No relevant results found.")

                    break  # Exit after first successful search

                except OrionSDKError as e:
                    print(f"  Search failed: {e}")
                    continue
        else:
            print("\n📝 No documents found in library. Upload some documents first!")
            print("\nTo upload a document, you can use:")
            print("  document = client.upload_document(")
            print("      file_path='./your_document.pdf',")
            print("      user_email='demo@example.com',")
            print("      description='Your document description'")
            print("  )")

        # Example 4: Show how to upload (commented out since we don't have test files)
        print("\n📤 Document upload example (commented out):")
        print("   # Uncomment and modify the path below to upload a real document")
        print("   # document = client.upload_document(")
        print("   #     file_path='./sample_document.pdf',")
        print("   #     user_email=user_email,")
        print("   #     description='Sample document for testing',")
        print("   #     wait_for_processing=True,  # Wait for processing to complete")
        print("   #     processing_timeout=300")
        print("   # )")
        print("   # print(f'Uploaded: {document.filename} (ID: {document.id})')")

        # Example 5: Get final library statistics
        print("\n📊 Final library statistics...")
        final_stats = client.get_library_stats(user_email)
        print(f"Documents: {final_stats.document_count}")
        print(f"Chunks with embeddings: {final_stats.chunks_with_embeddings}")
        print(f"Embedding coverage: {final_stats.embedding_coverage:.1f}%")

    except OrionSDKError as e:
        print(f"❌ SDK Error: {e}")
        if hasattr(e, "status_code"):
            print(f"   Status code: {e.status_code}")
        if hasattr(e, "details") and e.details:
            print(f"   Details: {e.details}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        # Always close the client
        client.close()
        print("\n✅ Client closed successfully")


if __name__ == "__main__":
    print("Orion SDK - Basic Usage Example")
    print("=" * 40)

    # Check if the Orion API is likely running
    print("Note: Make sure the Orion API is running on http://localhost:8000")
    print("You can start it with: uvicorn src.main:app --host 0.0.0.0 --port 8000")
    print()

    main()
