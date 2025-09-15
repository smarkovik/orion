# Text Chunking and Storage

This document describes how Orion chunks documents into smaller pieces for embedding generation and how these chunks are stored and managed.

## Overview

Text chunking is a critical step in the document processing pipeline that splits large documents into smaller, manageable pieces. This enables:

- **Efficient Embeddings**: Smaller text pieces generate more focused embeddings
- **Better Retrieval**: Relevant sections can be identified more precisely
- **Token Limits**: Respects embedding model token limits
- **Memory Management**: Prevents memory issues with large documents

## Chunking Strategy

### Token-Based Chunking

Orion uses **tiktoken** for intelligent token-based chunking rather than simple character or word splitting:

```python
# Configuration
chunk_size: int = 512          # Number of tokens per chunk
chunk_overlap_percent: float = 0.1    # 10% overlap between chunks
tiktoken_encoding: str = "cl100k_base"  # GPT-4 encoding
```

#### Why Token-Based?

- **Model Alignment**: Tokens match what embedding models actually process
- **Consistent Sizing**: Each chunk contains approximately the same amount of semantic content
- **Language Agnostic**: Works consistently across different languages
- **Precise Control**: Exact token count management

### Overlapping Chunks

#### Overlap Strategy

```
Chunk 1: [tokens 0-512]
Chunk 2: [tokens 461-973]    # 51 token overlap (10%)
Chunk 3: [tokens 922-1434]   # 51 token overlap (10%)
```

#### Benefits of Overlap

- **Context Preservation**: Important information spanning chunk boundaries isn't lost
- **Improved Retrieval**: Queries can match content even if it spans chunks
- **Semantic Continuity**: Maintains context across boundaries

### Chunking Process

#### 1. Text Preparation

```python
# Input: Converted text file
text_file_path = Path(context.metadata["converted_text_path"])
with open(text_file_path, "r", encoding="utf-8") as f:
    text_content = f.read()
```

#### 2. Token Encoding

```python
encoding = tiktoken.get_encoding(settings.tiktoken_encoding)
tokens = encoding.encode(text_content)
```

#### 3. Chunk Generation

```python
def _create_text_chunks(self, text: str, encoding: Any) -> List[str]:
    tokens = encoding.encode(text)
    chunk_size = settings.chunk_size
    overlap_size = int(chunk_size * settings.chunk_overlap_percent)

    chunks = []
    start = 0

    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)

        if end >= len(tokens):
            break

        start = end - overlap_size

    return chunks
```

## Chunk Storage

### File Organization

Each document's chunks are stored in the user's `raw_chunks` directory:

```
/app/orion/{user_email}/raw_chunks/
├── document_chunk_000.txt
├── document_chunk_001.txt
├── document_chunk_002.txt
└── ...
```

#### Naming Convention

```
{base_filename}_chunk_{sequence:03d}.txt
```

- **Base Filename**: Derived from the original document name
- **Sequence Number**: Zero-padded 3-digit sequence (000, 001, 002...)
- **Text Extension**: All chunks stored as `.txt` files

### Chunk Metadata

#### Chunk Information Stored

```python
chunk_files = []
for i, chunk in enumerate(chunks):
    chunk_filename = f"{base_filename}_chunk_{i:03d}.txt"
    chunk_path = chunks_dir / chunk_filename

    with open(chunk_path, "w", encoding="utf-8") as f:
        f.write(chunk)

    chunk_files.append(str(chunk_path))
```

#### Pipeline Context Updates

```python
context.metadata.update({
    "chunks_dir": str(chunks_dir),
    "chunk_count": len(chunks),
    "chunk_files": chunk_files,
})
```

## Chunk Processing for Embeddings

### Reading Chunks for Embedding

```python
chunk_files = list(chunks_dir.glob("*.txt"))
chunks_data = []

for chunk_file in sorted(chunk_files):
    with open(chunk_file, "r", encoding="utf-8") as f:
        chunk_text = f.read()

    chunks_data.append({
        "filename": chunk_file.name,
        "text": chunk_text,
        "token_count": len(tiktoken.get_encoding(settings.tiktoken_encoding).encode(chunk_text)),
    })
```

### Token Count Tracking

Each chunk's token count is calculated and stored:

- **Validation**: Ensures chunks are within expected size limits
- **Debugging**: Helps identify chunking issues
- **Optimization**: Enables chunk size optimization

## Configuration Options

### Chunk Size Configuration

```python
# Small chunks (better precision, more chunks)
chunk_size: int = 256

# Medium chunks (balanced)
chunk_size: int = 512  # Default

# Large chunks (better context, fewer chunks)
chunk_size: int = 1024
```

### Overlap Configuration

```python
# No overlap (risk of lost context)
chunk_overlap_percent: float = 0.0

# Light overlap (minimal redundancy)
chunk_overlap_percent: float = 0.05  # 5%

# Standard overlap (recommended)
chunk_overlap_percent: float = 0.1   # 10%

# Heavy overlap (maximum context preservation)
chunk_overlap_percent: float = 0.2   # 20%
```

### Encoding Configuration

```python
# GPT-4 / GPT-3.5 compatible (recommended)
tiktoken_encoding: str = "cl100k_base"

# GPT-3 compatible (legacy)
tiktoken_encoding: str = "p50k_base"
```

## Performance Characteristics

### Chunking Performance

- **Memory Efficient**: Processes text sequentially without loading everything into memory
- **Fast Processing**: Token-based operations are highly optimized
- **Scalable**: Performance scales linearly with document size

### Storage Performance

- **Individual Files**: Each chunk stored separately for easy access
- **Sequential Access**: Sorted file names enable ordered processing
- **Parallel Processing**: Chunks can be processed independently

## Error Handling

### Chunking Errors

```python
try:
    chunks = self._create_text_chunks(text_content, encoding)
except Exception as e:
    return StepResult(
        status=StepStatus.FAILED,
        message="Text chunking failed",
        error=str(e)
    )
```

### Storage Errors

- **Directory Creation**: Automatic creation with error handling
- **File Writing**: UTF-8 encoding with error handling
- **Permission Issues**: Appropriate error messages and logging

## Monitoring and Analytics

### Chunk Statistics

- **Chunk Count**: Number of chunks per document
- **Average Chunk Size**: Token count statistics
- **Processing Time**: Chunking performance metrics

### Quality Metrics

- **Token Distribution**: Ensure consistent chunk sizes
- **Overlap Effectiveness**: Monitor retrieval quality with different overlap settings
- **Storage Efficiency**: Track storage usage per document

## Best Practices

### Chunk Size Selection

- **Short Documents**: Use smaller chunks (256-512 tokens)
- **Long Documents**: Can use larger chunks (512-1024 tokens)
- **Technical Content**: Smaller chunks for precision
- **Narrative Content**: Larger chunks for context

### Overlap Optimization

- **Start with 10%**: Good default for most use cases
- **Increase for Important Content**: Use 15-20% for critical documents
- **Decrease for Storage Efficiency**: Use 5% when storage is a concern

### Encoding Choice

- **Modern Models**: Use `cl100k_base` (GPT-4 compatible)
- **Legacy Compatibility**: Use `p50k_base` if needed
- **Consistency**: Use the same encoding throughout the pipeline
