import json
import os
import time
import sys
from azure.ai.inference import EmbeddingsClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField, SearchField,
    SearchFieldDataType, VectorSearch, HnswAlgorithmConfiguration,
    VectorSearchProfile
)
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

# Load .env from the parent directory since this script lives in /scripts
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# ─────────────────────────────────────────────
# CLIENTS
# ─────────────────────────────────────────────

embedding_client = EmbeddingsClient(
    endpoint=os.getenv("FOUNDRY_EMBEDDING_ENDPOINT"),  # e.g. https://<your-project>.inference.ai.azure.com/models/<embedding-deployment-name>
    credential=AzureKeyCredential(os.getenv("FOUNDRY_API_KEY"))
)

index_client = SearchIndexClient(
    endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
    credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY"))
)

# ─────────────────────────────────────────────
# INDEX SCHEMA
# ─────────────────────────────────────────────

def create_index():
    fields = [
        SimpleField(name="psalm_id", type=SearchFieldDataType.String, key=True),   # e.g. "Psalm 1"
        SearchableField(name="text", type=SearchFieldDataType.String),              # full psalm text joined
        SearchableField(name="themes", type=SearchFieldDataType.String),            # joined array
        SearchableField(name="emotional_context", type=SearchFieldDataType.String), # joined array
        SearchableField(name="historical_usage", type=SearchFieldDataType.String),  # single string
        SearchableField(name="key_verses", type=SearchFieldDataType.String),        # joined array
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="psalm-vector-profile"
        )
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="psalm-hnsw")],
        profiles=[VectorSearchProfile(
            name="psalm-vector-profile",
            algorithm_configuration_name="psalm-hnsw"
        )]
    )

    index = SearchIndex(name="psalms-index", fields=fields, vector_search=vector_search)
    index_client.create_or_update_index(index)
    print("Index created.")

# ─────────────────────────────────────────────
# EMBEDDING
# ─────────────────────────────────────────────

def get_embedding(text: str) -> list:
    response = embedding_client.embed(
            input=[text],
            model=os.getenv("FOUNDRY_EMBEDDING_DEPLOYMENT")    # e.g. "text-embedding-ada-002" or "cohere-embed-v3"
        )
    return response.data[0].embedding

# ─────────────────────────────────────────────
# INDEXING
# ─────────────────────────────────────────────

def index_psalms():
    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "psalms-metadata.json")
    
    with open(data_path, "r", encoding="utf-8") as f:
        psalms = json.load(f)

    search_client = SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        index_name="psalms-index",
        credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY"))
    )

    documents = []

    for i, psalm in enumerate(psalms):
        # Join arrays into strings for both storage and embedding
        text_joined            = " ".join(psalm["text"])
        themes_joined          = ", ".join(psalm["themes"])
        emotional_context_joined = ", ".join(psalm["emotional_context"])
        key_verses_joined      = ", ".join(psalm["key_verses"])

        # Build the text we embed — emotional_context and themes drive similarity matching
        embed_text = (
            f"Emotional context: {emotional_context_joined}. "
            f"Themes: {themes_joined}. "
            f"Historical usage: {psalm['historical_usage']}. "
            f"Text: {text_joined}"
        )

        embedding = get_embedding(embed_text)

        documents.append({
            "psalm_id":         psalm["psalm_id"],
            "text":             text_joined,
            "themes":           themes_joined,
            "emotional_context": emotional_context_joined,
            "historical_usage": psalm["historical_usage"],
            "key_verses":       key_verses_joined,
            "embedding":        embedding
        })

        # Progress + rate limit protection
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(psalms)} psalms...")
            time.sleep(1)

    search_client.upload_documents(documents)
    print(f"Done. Indexed {len(documents)} psalms into 'psalms-index'.")


if __name__ == "__main__":
    print("Creating index...")
    create_index()
    print("Indexing psalms...")
    index_psalms()