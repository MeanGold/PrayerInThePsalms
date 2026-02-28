import os
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential

load_dotenv()

# ─────────────────────────────────────────────
# CONFIG: Switch between providers here
# Options: "azure_openai" or "foundry"
# ─────────────────────────────────────────────
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "azure_openai")


# ─────────────────────────────────────────────
# CLIENT SETUP
# ─────────────────────────────────────────────

def get_clients():
    """
    Returns (chat_client, embedding_client) depending on provider.
    For Foundry, both use the same azure-ai-inference client.
    For Azure OpenAI, both use the AzureOpenAI client.
    """
    if MODEL_PROVIDER == "foundry":
        from azure.ai.inference import ChatCompletionsClient, EmbeddingsClient
        from azure.core.credentials import AzureKeyCredential

        chat_client = ChatCompletionsClient(
            endpoint=os.getenv("FOUNDRY_CHAT_ENDPOINT"),       # e.g. https://<your-project>.inference.ai.azure.com/models/<deployment-name>
            credential=AzureKeyCredential(os.getenv("FOUNDRY_API_KEY"))
        )
        embedding_client = EmbeddingsClient(
            endpoint=os.getenv("FOUNDRY_EMBEDDING_ENDPOINT"),  # e.g. https://<your-project>.inference.ai.azure.com/models/<embedding-deployment-name>
            credential=AzureKeyCredential(os.getenv("FOUNDRY_API_KEY"))
        )
        return chat_client, embedding_client

    else:  # azure_openai (default)
        from openai import AzureOpenAI

        client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version="2024-02-01"
        )
        return client, client  # same client handles both chat + embeddings


chat_client, embedding_client = get_clients()


# ─────────────────────────────────────────────
# SEARCH CLIENT (same regardless of provider)
# ─────────────────────────────────────────────

search_client = SearchClient(
    endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
    index_name="psalms-index",
    credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY"))
)


# ─────────────────────────────────────────────
# EMBEDDING
# ─────────────────────────────────────────────

def get_embedding(text: str) -> list:
    if MODEL_PROVIDER == "foundry":
        response = embedding_client.embed(
            input=[text],
            model=os.getenv("FOUNDRY_EMBEDDING_DEPLOYMENT")    # e.g. "text-embedding-ada-002" or "cohere-embed-v3"
        )
        return response.data[0].embedding

    else:
        response = embedding_client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        return response.data[0].embedding


# ─────────────────────────────────────────────
# VECTOR SEARCH
# ─────────────────────────────────────────────

def search_psalms(user_feeling: str, top_k: int = 3) -> list:
    embedding = get_embedding(user_feeling)

    vector_query = VectorizedQuery(
        vector=embedding,
        k_nearest_neighbors=top_k,
        fields="embedding"
    )

    results = search_client.search(
        search_text=user_feeling,
        vector_queries=[vector_query],
        select=[                          # ← updated to match actual index fields
            "psalm_id",
            "text",
            "themes",
            "emotional_context",
            "historical_usage",
            "key_verses"
        ],
        top=top_k
    )

    return list(results)


def generate_recommendation(user_feeling: str) -> str:
    psalm_results = search_psalms(user_feeling)

    context = ""
    for r in psalm_results:
        context += f"""
{r['psalm_id']}
Themes: {r['themes']}
Emotional context: {r['emotional_context']}
Historical usage: {r['historical_usage']}
Key verses: {r['key_verses']}
Text: {r['text']}
---"""

    system_prompt = """You are a compassionate spiritual guide helping someone find psalms to pray through. 
You speak warmly and personally. Given how the person is feeling and relevant psalms retrieved for you, 
recommend 2-3 psalms with a brief, heartfelt explanation of why each one speaks to their situation. 
Reference specific verses when helpful. Keep your tone gentle, never preachy."""

    user_prompt = f"""The person shared: "{user_feeling}"

Here are relevant psalms to draw from:
{context}

Please recommend 2-3 of these psalms and explain why each one might speak to them right now."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    if MODEL_PROVIDER == "foundry":
        from azure.ai.inference.models import SystemMessage, UserMessage

        response = chat_client.complete(
            messages=[
                SystemMessage(content=system_prompt),
                UserMessage(content=user_prompt)
            ],
            model=os.getenv("FOUNDRY_CHAT_DEPLOYMENT"),        # e.g. "gpt-4o" or "Meta-Llama-3.1-70B-Instruct"
            temperature=0.7,
            max_tokens=800
        )
        return response.choices[0].message.content

    else:
        response = chat_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            max_tokens=800
        )
        return response.choices[0].message.content