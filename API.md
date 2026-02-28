# API Documentation - Psalm Recommendation RAG System

**Version**: 1.0  
**Base URL**: `https://{api-id}.execute-api.{region}.amazonaws.com/prod`

## Overview

The Psalm Recommendation API provides AI-powered psalm recommendations based on a user's emotional state. Users submit 1-2 sentences describing their feelings, and the system returns personalized psalm recommendations with contextual guidance using a RAG (Retrieval-Augmented Generation) pipeline powered by Amazon Bedrock.

**Requirements Validated**: 7.1, 7.2, 7.3

---

## Authentication

Currently, the API does not require authentication. For production deployments, consider adding:
- API Gateway API Keys
- AWS IAM authentication
- Custom authorizers (Lambda or Cognito)

---

## Endpoints

### POST /recommend

Get personalized psalm recommendations based on emotional input.

**Requirements**: 7.1, 7.2

#### Request

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "emotional_input": "string (1-2 sentences describing emotional state)"
}
```

**Parameters:**

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `emotional_input` | string | Yes | User's emotional state description | 1-2 sentences, non-empty |

**Example Request:**
```bash
curl -X POST https://abc123.execute-api.us-east-1.amazonaws.com/prod/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "emotional_input": "I am feeling anxious and worried about the future."
  }'
```

#### Response

**Success Response (200 OK):**

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "recommendations": [
    {
      "psalm_number": 23,
      "title": "The Lord is My Shepherd",
      "key_verses": [
        "The Lord is my shepherd, I lack nothing.",
        "Even though I walk through the darkest valley, I will fear no evil, for you are with me."
      ],
      "themes": ["comfort", "trust", "guidance", "protection"],
      "relevance_score": 0.92
    },
    {
      "psalm_number": 46,
      "title": "God is Our Refuge",
      "key_verses": [
        "God is our refuge and strength, an ever-present help in trouble.",
        "Be still, and know that I am God."
      ],
      "themes": ["refuge", "strength", "peace", "trust"],
      "relevance_score": 0.88
    }
  ],
  "personalized_message": "When you're feeling anxious about the future, these psalms remind us that God is our shepherd and refuge. Psalm 23 beautifully expresses how God guides and protects us even in uncertain times. The imagery of green pastures and quiet waters speaks to the peace He offers. Psalm 46 encourages us to 'be still' and trust in God's presence, even when circumstances feel chaotic. Take time to meditate on these verses and remember that you are not alone in your worries.",
  "processing_time_ms": 1247,
  "timestamp": "2024-01-15T10:30:45.123Z"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Unique identifier for the request (for tracking and debugging) |
| `recommendations` | array | List of recommended psalms (3-5 psalms) |
| `recommendations[].psalm_number` | integer | Psalm number (1-150) |
| `recommendations[].title` | string | Psalm title or first line |
| `recommendations[].key_verses` | array | Important verses from the psalm |
| `recommendations[].themes` | array | Thematic tags for the psalm |
| `recommendations[].relevance_score` | float | Similarity score (0.0-1.0, higher is more relevant) |
| `personalized_message` | string | AI-generated contextual guidance tailored to the user's emotional input |
| `processing_time_ms` | integer | Time taken to process the request in milliseconds |
| `timestamp` | string | ISO 8601 timestamp of the response |

---

## Error Responses

**Requirement**: 7.3

All error responses follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-15T10:30:45.123Z"
  }
}
```

### Error Codes

#### 400 Bad Request

**Cause**: Invalid request format or validation failure

**Example 1: Empty Input**
```json
{
  "error": {
    "code": "EMPTY_INPUT",
    "message": "Emotional input is required. Please provide 1-2 sentences describing your feelings.",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-15T10:30:45.123Z"
  }
}
```

**Example 2: Invalid Format**
```json
{
  "error": {
    "code": "INVALID_FORMAT",
    "message": "Request body must be valid JSON with an 'emotional_input' field.",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-15T10:30:45.123Z"
  }
}
```

**Example 3: Input Too Long**
```json
{
  "error": {
    "code": "INPUT_TOO_LONG",
    "message": "Emotional input should be 1-2 sentences. Please shorten your input.",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-15T10:30:45.123Z"
  }
}
```

#### 500 Internal Server Error

**Cause**: Server-side error during processing

**Example 1: Embedding Service Unavailable**
```json
{
  "error": {
    "code": "EMBEDDING_SERVICE_UNAVAILABLE",
    "message": "Unable to process your request at this time. Please try again in a few moments.",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-15T10:30:45.123Z"
  }
}
```

**Example 2: Vector Store Unavailable**
```json
{
  "error": {
    "code": "VECTOR_STORE_UNAVAILABLE",
    "message": "Unable to retrieve psalm recommendations at this time. Please try again later.",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-15T10:30:45.123Z"
  }
}
```

**Example 3: LLM Service Error**
```json
{
  "error": {
    "code": "LLM_SERVICE_ERROR",
    "message": "Unable to generate personalized message. Psalm recommendations are still available.",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-15T10:30:45.123Z",
    "recommendations": [
      {
        "psalm_number": 23,
        "title": "The Lord is My Shepherd",
        "key_verses": ["..."],
        "themes": ["comfort", "trust"],
        "relevance_score": 0.92
      }
    ]
  }
}
```

**Note**: When the LLM fails, the API returns psalm recommendations without the personalized message (Requirement 8.3).

#### 503 Service Unavailable

**Cause**: Service temporarily unavailable or under maintenance

```json
{
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "The service is temporarily unavailable. Please try again later.",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-15T10:30:45.123Z"
  }
}
```

#### 504 Gateway Timeout

**Cause**: Request exceeded timeout threshold (5 seconds)

```json
{
  "error": {
    "code": "REQUEST_TIMEOUT",
    "message": "The request took too long to process. Please try again.",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-15T10:30:45.123Z"
  }
}
```

---

## Example Requests and Responses

### Example 1: Anxiety and Worry

**Request:**
```bash
curl -X POST https://abc123.execute-api.us-east-1.amazonaws.com/prod/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "emotional_input": "I am feeling anxious and worried about the future."
  }'
```

**Response:**
```json
{
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "recommendations": [
    {
      "psalm_number": 23,
      "title": "The Lord is My Shepherd",
      "key_verses": [
        "The Lord is my shepherd, I lack nothing.",
        "Even though I walk through the darkest valley, I will fear no evil, for you are with me."
      ],
      "themes": ["comfort", "trust", "guidance", "protection"],
      "relevance_score": 0.92
    },
    {
      "psalm_number": 46,
      "title": "God is Our Refuge",
      "key_verses": [
        "God is our refuge and strength, an ever-present help in trouble.",
        "Be still, and know that I am God."
      ],
      "themes": ["refuge", "strength", "peace", "trust"],
      "relevance_score": 0.88
    },
    {
      "psalm_number": 91,
      "title": "Under His Wings",
      "key_verses": [
        "Whoever dwells in the shelter of the Most High will rest in the shadow of the Almighty.",
        "He will cover you with his feathers, and under his wings you will find refuge."
      ],
      "themes": ["protection", "trust", "safety", "deliverance"],
      "relevance_score": 0.85
    }
  ],
  "personalized_message": "When you're feeling anxious about the future, these psalms remind us that God is our shepherd and refuge. Psalm 23 beautifully expresses how God guides and protects us even in uncertain times. The imagery of green pastures and quiet waters speaks to the peace He offers. Psalm 46 encourages us to 'be still' and trust in God's presence, even when circumstances feel chaotic. Psalm 91 assures us of God's protective care, like a bird sheltering its young under its wings. Take time to meditate on these verses and remember that you are not alone in your worries.",
  "processing_time_ms": 1247,
  "timestamp": "2024-01-15T10:30:45.123Z"
}
```

### Example 2: Sadness and Depression

**Request:**
```bash
curl -X POST https://abc123.execute-api.us-east-1.amazonaws.com/prod/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "emotional_input": "I feel sad and depressed. Everything seems dark right now."
  }'
```

**Response:**
```json
{
  "request_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "recommendations": [
    {
      "psalm_number": 42,
      "title": "As the Deer Pants",
      "key_verses": [
        "As the deer pants for streams of water, so my soul pants for you, my God.",
        "Why, my soul, are you downcast? Why so disturbed within me? Put your hope in God."
      ],
      "themes": ["longing for God", "depression", "hope", "spiritual thirst"],
      "relevance_score": 0.94
    },
    {
      "psalm_number": 34,
      "title": "Taste and See",
      "key_verses": [
        "The Lord is close to the brokenhearted and saves those who are crushed in spirit.",
        "Taste and see that the Lord is good."
      ],
      "themes": ["comfort", "deliverance", "God's nearness", "brokenness"],
      "relevance_score": 0.89
    },
    {
      "psalm_number": 30,
      "title": "Joy Comes in the Morning",
      "key_verses": [
        "Weeping may stay for the night, but rejoicing comes in the morning.",
        "You turned my wailing into dancing."
      ],
      "themes": ["hope", "deliverance", "joy", "transformation"],
      "relevance_score": 0.86
    }
  ],
  "personalized_message": "In times of sadness and depression, the Psalms offer profound comfort and hope. Psalm 42 acknowledges the reality of feeling downcast while pointing us toward hope in God. The psalmist's honesty about their struggles reminds us that it's okay to bring our pain to God. Psalm 34 assures us that God is especially close to the brokenhearted—He doesn't distance Himself from our pain. Psalm 30 offers hope that this dark season won't last forever; joy will come again. Please know that these feelings are valid, and seeking support from trusted friends, family, or a counselor alongside spiritual encouragement is important.",
  "processing_time_ms": 1389,
  "timestamp": "2024-01-15T10:35:22.456Z"
}
```

### Example 3: Gratitude and Joy

**Request:**
```bash
curl -X POST https://abc123.execute-api.us-east-1.amazonaws.com/prod/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "emotional_input": "I am feeling grateful and joyful today. God has blessed me abundantly."
  }'
```

**Response:**
```json
{
  "request_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "recommendations": [
    {
      "psalm_number": 100,
      "title": "Shout for Joy",
      "key_verses": [
        "Shout for joy to the Lord, all the earth.",
        "Enter his gates with thanksgiving and his courts with praise."
      ],
      "themes": ["praise", "thanksgiving", "joy", "worship"],
      "relevance_score": 0.96
    },
    {
      "psalm_number": 103,
      "title": "Praise the Lord, My Soul",
      "key_verses": [
        "Praise the Lord, my soul, and forget not all his benefits.",
        "The Lord is compassionate and gracious, slow to anger, abounding in love."
      ],
      "themes": ["gratitude", "God's goodness", "blessing", "praise"],
      "relevance_score": 0.93
    },
    {
      "psalm_number": 145,
      "title": "Great is the Lord",
      "key_verses": [
        "Great is the Lord and most worthy of praise.",
        "The Lord is gracious and compassionate, slow to anger and rich in love."
      ],
      "themes": ["praise", "God's greatness", "thanksgiving", "worship"],
      "relevance_score": 0.91
    }
  ],
  "personalized_message": "What a beautiful place to be—filled with gratitude and joy! These psalms of praise help us express our thankfulness to God. Psalm 100 invites us to shout for joy and enter God's presence with thanksgiving. Psalm 103 encourages us to remember all of God's benefits and blessings, never taking them for granted. Psalm 145 celebrates God's greatness and goodness. In seasons of blessing, these psalms help us direct our joy and gratitude back to the One who gives every good gift. May your heart continue to overflow with praise!",
  "processing_time_ms": 1156,
  "timestamp": "2024-01-15T10:40:18.789Z"
}
```

### Example 4: Feeling Lost

**Request:**
```bash
curl -X POST https://abc123.execute-api.us-east-1.amazonaws.com/prod/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "emotional_input": "I feel lost and unsure of my purpose."
  }'
```

**Response:**
```json
{
  "request_id": "d4e5f6a7-b8c9-0123-def0-234567890123",
  "recommendations": [
    {
      "psalm_number": 139,
      "title": "You Have Searched Me",
      "key_verses": [
        "You have searched me, Lord, and you know me.",
        "Search me, God, and know my heart; test me and know my anxious thoughts."
      ],
      "themes": ["God's omniscience", "identity", "guidance", "intimacy with God"],
      "relevance_score": 0.91
    },
    {
      "psalm_number": 25,
      "title": "Show Me Your Ways",
      "key_verses": [
        "Show me your ways, Lord, teach me your paths.",
        "Guide me in your truth and teach me, for you are God my Savior."
      ],
      "themes": ["guidance", "trust", "seeking God", "direction"],
      "relevance_score": 0.87
    },
    {
      "psalm_number": 32,
      "title": "I Will Instruct You",
      "key_verses": [
        "I will instruct you and teach you in the way you should go.",
        "I will counsel you with my loving eye on you."
      ],
      "themes": ["guidance", "instruction", "God's care", "direction"],
      "relevance_score": 0.84
    }
  ],
  "personalized_message": "Feeling lost is a deeply human experience, and God meets us in these moments of uncertainty. Psalm 139 reminds us that even when we don't know ourselves fully, God knows us completely—He created us with purpose and intention. Psalm 25 teaches us to ask God for guidance and trust that He will show us the way. Psalm 32 contains God's beautiful promise: 'I will instruct you and teach you in the way you should go.' Your feelings of being lost don't mean you are lost to God. He sees you, knows you, and will guide you as you seek Him.",
  "processing_time_ms": 1298,
  "timestamp": "2024-01-15T10:45:33.012Z"
}
```

---

## Rate Limiting

**Current Configuration:**
- Rate Limit: 100 requests per second
- Burst Limit: 200 requests

Exceeding these limits will result in a `429 Too Many Requests` response:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please try again later.",
    "retry_after_seconds": 1,
    "timestamp": "2024-01-15T10:30:45.123Z"
  }
}
```

---

## Performance

**Requirement**: 7.4

- **Target Response Time**: < 5 seconds under normal load
- **Average Response Time**: 1-2 seconds
- **Timeout**: 10 seconds (Lambda timeout)

**Performance Metrics:**
- Embedding generation: ~200-500ms
- Vector search: ~100-300ms
- LLM generation: ~500-1500ms
- Total processing: ~1000-2500ms

---

## CORS Support

The API supports Cross-Origin Resource Sharing (CORS) with the following configuration:

**Allowed Origins**: `*` (all origins)  
**Allowed Methods**: `POST, OPTIONS`  
**Allowed Headers**: `Content-Type, X-Amz-Date, Authorization, X-Api-Key`

**Preflight Request Example:**
```bash
curl -X OPTIONS https://abc123.execute-api.us-east-1.amazonaws.com/prod/recommend \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type"
```

---

## Privacy and Security

**Requirements**: 9.1, 9.2, 9.3, 9.4

### Data Privacy

- **User Input**: Not persisted beyond request duration
- **Logging**: PII is sanitized from logs
- **Encryption**: All API communications use HTTPS (TLS 1.2+)
- **Third Parties**: User input only shared with required AWS services (Bedrock)

### Security Best Practices

For production deployments:

1. **Add Authentication**: Implement API Gateway authorizers
2. **Use API Keys**: Require API keys for access
3. **Enable WAF**: Use AWS WAF for additional protection
4. **Monitor Usage**: Set up CloudWatch alarms for unusual activity
5. **Restrict CORS**: Limit allowed origins to your domain

---

## Monitoring and Debugging

### Request ID

Every response includes a `request_id` field. Use this ID to:
- Track requests in CloudWatch Logs
- Debug issues with specific requests
- Correlate errors across services

### CloudWatch Logs

Logs are available in:
- `/aws/lambda/psalm-recommendation-handler`

Search logs by request ID:
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/psalm-recommendation-handler \
  --filter-pattern "request_id_here"
```

### CloudWatch Metrics

Custom metrics are emitted to namespace `PsalmRecommendationRAG`:
- `RequestCount` - Total requests
- `SuccessCount` - Successful requests
- `ErrorCount` - Failed requests
- `ProcessingTime` - Request processing time
- `EmbeddingGenerationSuccess` - Successful embedding generations
- `EmbeddingGenerationFailure` - Failed embedding generations
- `LLMInvocationSuccess` - Successful LLM invocations
- `LLMInvocationFailure` - Failed LLM invocations

---

## SDK Examples

### Python

```python
import requests
import json

API_ENDPOINT = "https://abc123.execute-api.us-east-1.amazonaws.com/prod/recommend"

def get_psalm_recommendation(emotional_input):
    """Get psalm recommendations based on emotional input."""
    
    payload = {
        "emotional_input": emotional_input
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(API_ENDPOINT, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response: {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        return None

# Example usage
result = get_psalm_recommendation("I am feeling anxious and worried.")
if result:
    print(f"Request ID: {result['request_id']}")
    print(f"\nRecommendations:")
    for rec in result['recommendations']:
        print(f"  - Psalm {rec['psalm_number']}: {rec['title']}")
    print(f"\nMessage: {result['personalized_message']}")
```

### JavaScript (Node.js)

```javascript
const axios = require('axios');

const API_ENDPOINT = 'https://abc123.execute-api.us-east-1.amazonaws.com/prod/recommend';

async function getPsalmRecommendation(emotionalInput) {
  try {
    const response = await axios.post(API_ENDPOINT, {
      emotional_input: emotionalInput
    }, {
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    return response.data;
  } catch (error) {
    if (error.response) {
      console.error('HTTP Error:', error.response.status);
      console.error('Response:', error.response.data);
    } else {
      console.error('Request Error:', error.message);
    }
    return null;
  }
}

// Example usage
(async () => {
  const result = await getPsalmRecommendation('I am feeling anxious and worried.');
  if (result) {
    console.log(`Request ID: ${result.request_id}`);
    console.log('\nRecommendations:');
    result.recommendations.forEach(rec => {
      console.log(`  - Psalm ${rec.psalm_number}: ${rec.title}`);
    });
    console.log(`\nMessage: ${result.personalized_message}`);
  }
})();
```

### cURL

```bash
#!/bin/bash

API_ENDPOINT="https://abc123.execute-api.us-east-1.amazonaws.com/prod/recommend"
EMOTIONAL_INPUT="I am feeling anxious and worried."

curl -X POST "$API_ENDPOINT" \
  -H "Content-Type: application/json" \
  -d "{\"emotional_input\": \"$EMOTIONAL_INPUT\"}" \
  | jq '.'
```

---

## Changelog

### Version 1.0 (2024-01-15)
- Initial API release
- POST /recommend endpoint
- Support for emotional input processing
- RAG-based psalm recommendations
- Personalized message generation
- Error handling and fallback mechanisms

---

## Support

For issues or questions:

1. **Check CloudWatch Logs**: Use the request ID to find detailed logs
2. **Review Error Codes**: See the Error Responses section above
3. **Check Service Health**: Verify AWS service status
4. **Consult Documentation**: Review [DEPLOYMENT.md](DEPLOYMENT.md) and [infrastructure/README.md](infrastructure/README.md)

---

## Additional Resources

- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
- [infrastructure/README.md](infrastructure/README.md) - Infrastructure documentation
- [scripts/README.md](scripts/README.md) - Deployment scripts documentation
- [Requirements Document](.kiro/specs/psalm-recommendation-rag/requirements.md)
- [Design Document](.kiro/specs/psalm-recommendation-rag/design.md)
- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
