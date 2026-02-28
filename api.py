from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from recommend import generate_recommendation
import json

app = FastAPI()

# Required so your React app (on a different port) can talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load psalms data
with open('psalms.json', 'r', encoding='utf-8') as f:
    psalms_data = json.load(f)

with open('psalms-metadata.json', 'r', encoding='utf-8') as f:
    psalms_metadata = json.load(f)

class MessageRequest(BaseModel):
    message: str

class MessageResponse(BaseModel):
    recommendation: str

@app.post("/recommend", response_model=MessageResponse)
async def recommend(request: MessageRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    recommendation = generate_recommendation(request.message)
    return MessageResponse(recommendation=recommendation)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/psalms")
async def get_all_psalms():
    """Get list of all psalms with metadata"""
    return {"psalms": psalms_metadata}

@app.get("/psalms/{psalm_number}")
async def get_psalm(psalm_number: int):
    """Get full text of a specific psalm"""
    # Find metadata for this psalm
    metadata = next((p for p in psalms_metadata if p.get('psalm_id') == f"Psalm {psalm_number}"), None)
    
    if not metadata:
        raise HTTPException(status_code=404, detail=f"Psalm {psalm_number} not found")
    
    # Extract psalm text from psalms.json
    psalm_lines = []
    current_verse = None
    
    for item in psalms_data:
        if item.get('type') == 'line text' and item.get('chapterNumber') == psalm_number:
            verse_num = item.get('verseNumber')
            text = item.get('value', '').strip()
            
            if verse_num != current_verse:
                current_verse = verse_num
                psalm_lines.append(f"{verse_num}. {text}")
            else:
                psalm_lines[-1] += text
    
    if not psalm_lines:
        raise HTTPException(status_code=404, detail=f"Psalm {psalm_number} text not found")
    
    return {
        "psalm_number": psalm_number,
        "psalm_id": metadata.get('psalm_id'),
        "text": metadata.get('text', []),
        "themes": metadata.get('themes', []),
        "emotional_context": metadata.get('emotional_context', []),
        "historical_usage": metadata.get('historical_usage', ''),
        "key_verses": metadata.get('key_verses', [])
    }