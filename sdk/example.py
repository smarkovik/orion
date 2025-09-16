#!/usr/bin/env python3
"""
Main example for the Orion SDK.

This is the primary example file that demonstrates the complete Orion SDK workflow.
It shows how to:
1. Initialize the client
2. Upload documents
3. Wait for processing
4. Perform searches
5. Handle errors gracefully
"""

import sys
import time
from pathlib import Path

# Import the Orion SDK
from orion_sdk import DocumentUploadError, OrionClient, OrionSDKError, ProcessingStatus, QueryError, ValidationError


def create_sample_document():
    """Create a sample document for demonstration."""
    sample_content = """
    Artificial Intelligence and Machine Learning in Modern Software Development

    Introduction
    
    Artificial Intelligence (AI) and Machine Learning (ML) have revolutionized the way we approach 
    software development. These technologies enable systems to learn from data, make predictions, 
    and improve their performance over time without being explicitly programmed for every scenario.

    Core Concepts
    
    Machine learning encompasses several key areas:
    
    1. Supervised Learning: Uses labeled training data to learn a mapping from inputs to outputs.
       Common algorithms include linear regression, decision trees, and neural networks.
    
    2. Unsupervised Learning: Finds hidden patterns in data without labeled examples.
       Techniques include clustering, dimensionality reduction, and association rules.
    
    3. Reinforcement Learning: Learns through interaction with an environment, receiving 
       rewards or penalties for actions taken.

    Applications in Software Development
    
    AI and ML are being integrated into various aspects of software development:
    
    - Code Generation: AI can help generate code snippets and suggest improvements
    - Testing: Automated test case generation and bug detection
    - Documentation: Automatic generation of documentation from code
    - Performance Optimization: ML models can predict and optimize system performance
    - Security: Anomaly detection and threat identification
    
    Popular Tools and Frameworks
    
    - TensorFlow: Open-source library for machine learning and deep learning
    - PyTorch: Dynamic neural network framework popular in research
    - Scikit-learn: Simple and efficient tools for data mining and analysis
    - OpenAI API: Provides access to advanced language models
    - Hugging Face: Platform for sharing and using pre-trained models
    
    Challenges and Considerations
    
    While AI/ML offers tremendous opportunities, developers must consider:
    
    - Data Quality: Models are only as good as the data they're trained on
    - Bias and Fairness: Ensuring AI systems don't perpetuate harmful biases
    - Interpretability: Understanding how models make decisions
    - Scalability: Deploying models efficiently in production environments
    - Ethics: Responsible AI development and deployment
    
    Future Trends
    
    The field continues to evolve with trends like:
    - Large Language Models (LLMs) becoming more accessible
    - Edge AI for real-time processing on devices
    - AutoML for democratizing machine learning
    - Federated learning for privacy-preserving ML
    - Quantum machine learning for complex problem solving
    
    Conclusion
    
    AI and ML are transforming software development, offering new possibilities for creating 
    intelligent, adaptive systems. As these technologies continue to mature, developers who 
    understand and can leverage them will be well-positioned to build the next generation 
    of software applications.
    """

    # Create sample document
    sample_file = Path("sample_ai_ml_document.txt")
    with open(sample_file, "w", encoding="utf-8") as f:
        f.write(sample_content.strip())

    print(f"✅ Created sample document: {sample_file}")
    return sample_file


def main():
    """Main demonstration function."""
    print("🚀 Orion SDK - Complete Example")
    print("=" * 50)
    print()

    # Configuration
    api_base_url = "http://localhost:8000"
    user_email = "demo@example.com"

    print(f"📡 API URL: {api_base_url}")
    print(f"👤 User: {user_email}")
    print()

    # Initialize the Orion client
    print("🔧 Initializing Orion SDK client...")
    try:
        client = OrionClient(base_url=api_base_url, timeout=30)
        print("✅ Client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return

    sample_file = None

    try:
        # Step 1: Check initial library state
        print("\n📊 Checking initial library state...")
        try:
            initial_stats = client.get_library_stats(user_email)
            print(f"   Library exists: {initial_stats.exists}")
            if initial_stats.exists:
                print(f"   Documents: {initial_stats.document_count}")
                print(f"   Chunks: {initial_stats.chunk_count}")
                print(f"   Embeddings: {initial_stats.chunks_with_embeddings}")
                print(f"   Size: {initial_stats.total_file_size_mb:.1f}MB")
        except Exception as e:
            print(f"   ⚠️ Could not get initial stats: {e}")
            initial_stats = None

        # Step 2: Get supported algorithms
        print("\n🔍 Getting supported search algorithms...")
        try:
            algorithms = client.get_supported_algorithms()
            print(f"   Available: {', '.join(algorithms)}")
            default_algorithm = algorithms[0] if algorithms else "cosine"
        except Exception as e:
            print(f"   ⚠️ Could not get algorithms: {e}")
            default_algorithm = "cosine"

        # Step 3: Create and upload a sample document
        print("\n📝 Creating sample document...")
        sample_file = create_sample_document()

        print("\n📤 Uploading document to Orion...")
        try:
            document = client.upload_document(
                file_path=sample_file,
                user_email=user_email,
                description="AI/ML article for SDK demonstration",
                wait_for_processing=False,  # We'll check status manually
            )

            print(f"✅ Upload successful!")
            print(f"   Document ID: {document.id}")
            print(f"   Filename: {document.filename}")
            print(f"   Size: {document.file_size} bytes")
            print(f"   Status: {document.processing_status.value}")

        except ValidationError as e:
            print(f"❌ Validation error: {e}")
            return
        except DocumentUploadError as e:
            print(f"❌ Upload failed: {e}")
            return
        except Exception as e:
            print(f"❌ Unexpected error during upload: {e}")
            return

        # Step 4: Wait for processing
        print("\n⏳ Waiting for document processing...")
        print("   This includes text extraction, chunking, and embedding generation...")

        max_wait_time = 90  # 90 seconds
        check_interval = 10  # Check every 10 seconds
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            try:
                current_stats = client.get_library_stats(user_email)

                if initial_stats and current_stats.chunks_with_embeddings > initial_stats.chunks_with_embeddings:
                    print("✅ New embeddings detected - processing appears complete!")
                    break
                elif not initial_stats and current_stats.chunks_with_embeddings > 0:
                    print("✅ Embeddings found - processing appears complete!")
                    break
                else:
                    elapsed = time.time() - start_time
                    print(f"   ⏱️ Still processing... ({elapsed:.0f}s elapsed, checking again in {check_interval}s)")
                    time.sleep(check_interval)

            except Exception as e:
                print(f"   ⚠️ Error checking status: {e}")
                time.sleep(check_interval)
        else:
            print(f"   ⏰ Processing taking longer than {max_wait_time}s, but continuing...")

        # Step 5: Perform searches
        print("\n🔎 Performing semantic searches...")

        search_queries = [
            ("machine learning algorithms", "Should find ML content with high relevance"),
            ("neural networks and deep learning", "Should find AI-specific content"),
            ("software development tools", "Should find development-related content"),
            ("data quality and bias", "Should find content about ML challenges"),
            ("TensorFlow and PyTorch", "Should find content about ML frameworks"),
            ("cooking recipes", "Should find no relevant results"),
        ]

        for i, (query, expected) in enumerate(search_queries, 1):
            print(f"\n   Query {i}: '{query}'")
            print(f"   Expected: {expected}")

            try:
                response = client.search(query=query, user_email=user_email, algorithm=default_algorithm, limit=3)

                print(f"   ✅ Found {len(response.results)} results in {response.execution_time:.3f}s")
                print(
                    f"      Searched {response.total_chunks_searched} chunks from {response.total_documents_searched} documents"
                )

                if response.results:
                    for j, result in enumerate(response.results, 1):
                        print(f"      {j}. Score: {result.similarity_score:.3f} | File: {result.original_filename}")
                        # Show a snippet of the text
                        text_snippet = result.text.replace("\n", " ").strip()[:100]
                        print(f"         Text: {text_snippet}...")
                else:
                    print("      No relevant results found")

            except QueryError as e:
                print(f"   ❌ Search failed: {e}")
            except Exception as e:
                print(f"   ❌ Unexpected search error: {e}")

        # Step 6: Final library statistics
        print("\n📊 Final library statistics...")
        try:
            final_stats = client.get_library_stats(user_email)
            print(f"   📚 Total documents: {final_stats.document_count}")
            print(f"   📄 Total chunks: {final_stats.chunk_count}")
            print(f"   🧮 Chunks with embeddings: {final_stats.chunks_with_embeddings}")
            print(f"   📊 Embedding coverage: {final_stats.embedding_coverage:.1f}%")
            print(f"   💾 Total size: {final_stats.total_file_size_mb:.1f}MB")

            if final_stats.chunk_count > 0:
                print(f"   📈 Average chunks per document: {final_stats.avg_chunks_per_document:.1f}")

        except Exception as e:
            print(f"   ⚠️ Could not get final stats: {e}")

        print("\n✅ Example completed successfully!")

    except KeyboardInterrupt:
        print("\n⏹️ Example interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")

        # Close the client
        try:
            client.close()
            print("✅ Client closed")
        except Exception as e:
            print(f"⚠️ Error closing client: {e}")

        # Remove sample file
        if sample_file and sample_file.exists():
            try:
                sample_file.unlink()
                print("✅ Sample document removed")
            except Exception as e:
                print(f"⚠️ Could not remove sample file: {e}")


if __name__ == "__main__":
    print("Orion SDK Example")
    print("This example demonstrates the complete Orion workflow:")
    print("- Document upload")
    print("- Processing pipeline")
    print("- Semantic search")
    print("- Library management")
    print()
    print("Prerequisites:")
    print("- Orion API running on http://localhost:8000")
    print("- Cohere API key configured in the Orion API")
    print()

    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        sys.exit(1)
