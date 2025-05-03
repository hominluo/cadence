from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

# Allow your static site on localhost:3000 to access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

QA_BACKEND_URL = "http://localhost:8000/v2/answer"

@app.post("/v2/answer")
async def proxy_to_backend(req: Request):
    body = await req.json()
    async with httpx.AsyncClient() as client:
        r = await client.post(QA_BACKEND_URL, json=body)
        return r.json()