import uvicorn
from config import settings

if __name__ == "__main__":
    print(f"[OnBoarding Buddy] Starting Server at http://{settings.HOST}:{settings.PORT} (env={settings.ENVIRONMENT}, debug={settings.DEBUG})")
    uvicorn.run(
        "server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
