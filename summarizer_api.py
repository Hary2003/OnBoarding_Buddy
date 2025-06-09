from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import pipeline, AutoTokenizer

app = FastAPI()

tokenizer = AutoTokenizer.from_pretrained("facebook/bart-large-cnn")
summarizer = pipeline("summarization", model="facebook/bart-large-cnn", tokenizer=tokenizer, device=-1)  # CPU

class CodeRequest(BaseModel):
    code: str

@app.post("/summarize")
async def summarize_code(request: CodeRequest):
    code = request.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Code input is empty")
    
    # Truncate input to 512 tokens max to prevent index errors
    tokens = tokenizer.tokenize(code)
    if len(tokens) > 512:
        code = tokenizer.convert_tokens_to_string(tokens[:512])
    
    try:
        summary = summarizer(code, max_length=60, min_length=20, do_sample=False)
        return {"summary": summary[0]["summary_text"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization error: {e}")
