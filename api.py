from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from recommend import generate_recommendation

app = FastAPI()

# Required so your React app (on a different port) can talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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