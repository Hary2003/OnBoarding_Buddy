import uvicorn
from config import settings

if __name__ == "__main__":
    print(f"[OnBoarding Buddy] Starting Server at http://{settings.HOST}:{settings.PORT}")
    uvicorn.run("server:app", host=settings.HOST, port=settings.PORT, reload=True)
