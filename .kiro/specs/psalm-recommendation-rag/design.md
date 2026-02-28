# Design Document: Psalm Recommendation RAG

## Overview

This feature provides an AI-powered application that helps users discover relevant psalms based on their emotional state. Users input 1-2 sentences describing how they're feeling, and the system returns personalized psalm recommendations with warm, contextual guidance. The solution leverages Amazon Bedrock's Knowledge Bases feature with a RAG (Retrieval-Augmented Generation) pipeline to semantically match user emotions with appropriate psalms from a vector store containing rich psalm metadata including themes, emotional context, historical usage, and key verses.

The architecture uses Amazon Bedrock for both embedding generation and LLM inference, with vector storage backed by either Amazon OpenSearch Serverless or Aurora. The system retrieves semantically similar psalms based on the user's emotional input, then passes these as context to an LLM to generate personalized, empathetic recommendations that feel natural and supportive.

## Architecture

```mermaid
graph TD
    A[User Input: Emotional State] --> B[API Gateway]
    B --> C[Lambda: Request Handler]
    C --> D[Amazon Bedrock: Embedding Model]
    D --> E[Vector Search]
    E --> F[Knowledge Base: Psalm Vectors]
    F --> E
    E --> G[Retrieved Psalms Context]
    G --> H[Amazon Bedrock: LLM]
    H --> I[Personalized Response]
    I --> C
    C --> B
    B --> J[User: Psalm Recommendations]
    
    K[Psalm Data Ingestion] --> L[Lambda: Data Processor]
    L --> M[Amazon Bedrock: Embedding Model]
    M --> N[Vector Store]
    N --> F
    
    style F fill:#e1f5ff
    style H fill:#ffe1f5
    style D fill:#ffe1f5
