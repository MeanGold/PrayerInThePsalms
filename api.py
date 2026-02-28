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
    # Transform psalm_id from "Psalm-1" to "Psalm 1" for frontend display
    psalms_list = []
    for psalm in psalms_metadata:
        psalm_copy = psalm.copy()
        # Convert "Psalm-1" to "Psalm 1"
        psalm_id = psalm_copy.get('psalm_id', '')
        if psalm_id.startswith('Psalm-'):
            psalm_copy['psalm_id'] = psalm_id.replace('Psalm-', 'Psalm ')
        psalms_list.append(psalm_copy)
    
    return {"psalms": psalms_list}

@app.get("/psalms/{psalm_number}")
async def get_psalm(psalm_number: int):
    """Get full text of a specific psalm"""
    # Find metadata for this psalm (note: psalm_id format is "Psalm-1" not "Psalm 1")
    metadata = next((p for p in psalms_metadata if p.get('psalm_id') == f"Psalm-{psalm_number}"), None)
    
    if not metadata:
        raise HTTPException(status_code=404, detail=f"Psalm {psalm_number} not found")
    
    # Extract psalm text from psalms.json and aggregate by verse
    psalm_verses = {}
    
    for item in psalms_data:
        if item.get('type') == 'line text' and item.get('chapterNumber') == psalm_number:
            verse_num = item.get('verseNumber')
            text = item.get('value', '').strip()
            
            if verse_num not in psalm_verses:
                psalm_verses[verse_num] = text
            else:
                psalm_verses[verse_num] += ' ' + text
    
    # Convert to sorted list with verse numbers
    psalm_lines = [f"{verse}. {text}" for verse, text in sorted(psalm_verses.items())]
    
    # If no text found in psalms.json, fall back to metadata text
    if not psalm_lines:
        psalm_lines = metadata.get('text', [])
    
    return {
        "psalm_number": psalm_number,
        "psalm_id": f"Psalm {psalm_number}",
        "text": psalm_lines,
        "themes": metadata.get('themes', []),
        "emotional_context": metadata.get('emotional_context', []),
        "historical_usage": metadata.get('historical_usage', ''),
        "key_verses": metadata.get('key_verses', [])
    }