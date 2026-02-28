import json
import os
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField, SearchField,
    SearchFieldDataType, VectorSearch, HnswAlgorithmConfiguration,
    VectorSearchProfile, HnswParameters
)
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

load_dotenv()

# Clients
openai_client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-02-01"
)

index_client = SearchIndexClient(
    endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
    credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY"))
)

# Create the index schema
def create_index():
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="psalm_number", type=SearchFieldDataType.Int32, filterable=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="themes", type=SearchFieldDataType.String),
        SearchableField(name="emotional_context", type=SearchFieldDataType.String),
        SearchableField(name="key_verses", type=SearchFieldDataType.String),
        SearchableField(name="summary", type=SearchFieldDataType.String),
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
        profiles=[VectorSearchProfile(name="psalm-vector-profile", algorithm_configuration_name="psalm-hnsw")]
    )
    
    index = SearchIndex(name="psalms-index", fields=fields, vector_search=vector_search)
    index_client.create_or_update_index(index)
    print("Index created.")

# Generate embedding for a piece of text
def get_embedding(text):
    response = openai_client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

# Index all psalms
def index_psalms():
    with open("psalms.json", "r") as f:
        psalms = json.load(f)
    
    search_client = SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        index_name="psalms-index",
        credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY"))
    )
    
    documents = []
    for psalm in psalms:
        # Embed the emotional_context + themes together for richest matching
        embed_text = f"{psalm['emotional_context']} Themes: {psalm['themes']} {psalm['summary']}"
        embedding = get_embedding(embed_text)
        
        documents.append({**psalm, "themes": ", ".join(psalm["themes"]), "embedding": embedding})
    
    search_client.upload_documents(documents)
    print(f"Indexed {len(documents)} psalms.")

create_index()
index_psalms()