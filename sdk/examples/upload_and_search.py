#!/usr/bin/env python3
"""
Complete workflow example: Upload documents and search them.

This example demonstrates:
- Uploading multiple documents
- Waiting for processing
- Performing various searches
- Handling errors gracefully
"""

import sys
import time
from pathlib import Path

# Add the SDK to the path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from orion_sdk import OrionClient, OrionSDKError, ValidationError


def create_sample_documents():
    """Create sample text documents for testing."""
    sample_docs_dir = Path("sample_docs")
    sample_docs_dir.mkdir(exist_ok=True)

    documents = {
        "machine_learning.txt": """
        Machine Learning and Artificial Intelligence

        Machine learning is a subset of artificial intelligence (AI) that focuses on 
        algorithms that can learn and make predictions from data. It encompasses various 
        techniques including supervised learning, unsupervised learning, and reinforcement learning.

        Key concepts in machine learning include:
        - Training data and test data
        - Feature engineering and selection
        - Model validation and cross-validation
        - Overfitting and underfitting
        - Bias-variance tradeoff

        Popular algorithms include decision trees, random forests, support vector machines,
        neural networks, and deep learning models. These are used in applications like
        image recognition, natural language processing, recommendation systems, and
        autonomous vehicles.
        """,
        "data_science.txt": """
        Data Science and Analytics

        Data science is an interdisciplinary field that combines statistics, computer science,
        and domain expertise to extract insights from structured and unstructured data.

        The data science process typically includes:
        1. Data collection and acquisition
        2. Data cleaning and preprocessing
        3. Exploratory data analysis
        4. Feature engineering
        5. Model building and validation
        6. Deployment and monitoring

        Key tools and technologies include Python, R, SQL, Jupyter notebooks, pandas,
        scikit-learn, TensorFlow, and various cloud platforms. Data scientists work
        with big data technologies like Hadoop, Spark, and distributed computing
        frameworks to handle large-scale datasets.
        """,
        "software_engineering.txt": """
        Software Engineering Best Practices

        Software engineering is the systematic approach to the design, development,
        and maintenance of large-scale software systems. It involves applying
        engineering principles to create reliable, efficient, and maintainable software.

        Core principles include:
        - Modularity and separation of concerns
        - Code reusability and maintainability
        - Testing and quality assurance
        - Version control and collaboration
        - Documentation and code readability

        Development methodologies like Agile, Scrum, and DevOps have revolutionized
        how teams build software. Modern practices include continuous integration,
        continuous deployment, microservices architecture, and cloud-native development.
        """,
    }

    created_files = []
    for filename, content in documents.items():
        file_path = sample_docs_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content.strip())
        created_files.append(file_path)
        print(f"✅ Created sample document: {file_path}")

    return created_files


def main():
    """Main example function."""
    print("🚀 Initializing Orion client...")
    client = OrionClient(base_url="http://localhost:8000")

    user_email = "test@example.com"

    try:
        # Step 1: Create sample documents
        print("\n📝 Creating sample documents...")
        sample_files = create_sample_documents()

        # Step 2: Upload documents
        print(f"\n📤 Uploading {len(sample_files)} documents...")
        uploaded_docs = []

        for file_path in sample_files:
            try:
                print(f"Uploading: {file_path.name}")
                document = client.upload_document(
                    file_path=file_path,
                    user_email=user_email,
                    description=f"Sample document: {file_path.stem}",
                    wait_for_processing=False,  # Don't wait initially
                )
                uploaded_docs.append(document)
                print(f"  ✅ Uploaded: {document.id}")

            except ValidationError as e:
                print(f"  ❌ Validation error: {e}")
            except OrionSDKError as e:
                print(f"  ❌ Upload error: {e}")

        if not uploaded_docs:
            print("❌ No documents were uploaded successfully")
            return

        # Step 3: Wait for processing
        print(f"\n⏳ Waiting for documents to be processed...")
        print("Note: Processing includes text extraction, chunking, and embedding generation")
        print("This may take 30-60 seconds depending on document size and API performance...")

        # Wait a bit for processing to start
        time.sleep(10)

        # Check library stats periodically
        max_wait_time = 120  # 2 minutes
        check_interval = 10  # 10 seconds
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            stats = client.get_library_stats(user_email)
            print(f"  Documents: {stats.document_count}, Chunks with embeddings: {stats.chunks_with_embeddings}")

            if stats.chunks_with_embeddings > 0:
                print("✅ Processing appears to be complete!")
                break

            print(f"  Still processing... (waiting {check_interval}s)")
            time.sleep(check_interval)
        else:
            print("⚠️  Processing is taking longer than expected, but continuing with search attempts...")

        # Step 4: Perform searches
        print("\n🔍 Performing searches...")

        search_queries = [
            ("machine learning algorithms", "Should find ML content"),
            ("data preprocessing steps", "Should find data science content"),
            ("software development practices", "Should find software engineering content"),
            ("neural networks and deep learning", "Should find AI/ML content"),
            ("testing and quality assurance", "Should find software engineering content"),
            ("completely unrelated topic like cooking", "Should find no or low-relevance results"),
        ]

        for query, description in search_queries:
            print(f"\n🔎 Query: '{query}'")
            print(f"   Expected: {description}")

            try:
                response = client.search(query=query, user_email=user_email, algorithm="cosine", limit=5)

                print(f"   Results: {len(response.results)} found in {response.execution_time:.3f}s")
                print(
                    f"   Searched: {response.total_chunks_searched} chunks from {response.total_documents_searched} documents"
                )

                if response.results:
                    for i, result in enumerate(response.results[:3], 1):  # Show top 3
                        print(f"     {i}. Score: {result.similarity_score:.3f} | File: {result.original_filename}")
                        print(f"        Text: {result.text[:80]}...")
                else:
                    print("     No results found")

            except OrionSDKError as e:
                print(f"   ❌ Search failed: {e}")

        # Step 5: Final statistics
        print("\n📊 Final library statistics:")
        final_stats = client.get_library_stats(user_email)
        print(f"  Total documents: {final_stats.document_count}")
        print(f"  Total chunks: {final_stats.chunk_count}")
        print(f"  Chunks with embeddings: {final_stats.chunks_with_embeddings}")
        print(f"  Embedding coverage: {final_stats.embedding_coverage:.1f}%")
        print(f"  Total library size: {final_stats.total_file_size_mb:.1f}MB")

        if final_stats.chunk_count > 0:
            print(f"  Average chunks per document: {final_stats.avg_chunks_per_document:.1f}")

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Clean up
        client.close()
        print("\n🧹 Cleaning up sample documents...")
        try:
            import shutil

            shutil.rmtree("sample_docs")
            print("✅ Cleaned up sample documents")
        except Exception as e:
            print(f"⚠️  Could not clean up sample documents: {e}")

        print("✅ Example completed")


if __name__ == "__main__":
    print("Orion SDK - Upload and Search Example")
    print("=" * 45)
    print()
    print("This example will:")
    print("1. Create sample text documents")
    print("2. Upload them to Orion")
    print("3. Wait for processing")
    print("4. Perform various searches")
    print("5. Show library statistics")
    print()
    print("Make sure the Orion API is running on http://localhost:8000")
    print()

    input("Press Enter to continue...")
    main()
