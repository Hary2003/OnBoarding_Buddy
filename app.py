import argparse
import uvicorn
from config import settings


def main():
    parser = argparse.ArgumentParser(description="OnBoarding Buddy Backend Server")
    parser.add_argument("--host", default=settings.HOST, help="Host address to bind Uvicorn")
    parser.add_argument("--port", type=int, default=settings.PORT, help="Port to bind Uvicorn")
    parser.add_argument("--reload", dest="reload", action="store_true", default=None, help="Enable auto-reload")
    parser.add_argument("--no-reload", dest="reload", action="store_false", help="Disable auto-reload")
    args, _ = parser.parse_known_args()

    host = args.host
    port = args.port
    reload_enabled = args.reload if args.reload is not None else settings.RELOAD

    print(f"[OnBoarding Buddy] Starting Server at http://{host}:{port} (env={settings.ENVIRONMENT}, debug={settings.DEBUG})")
    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=reload_enabled,
        log_level=settings.LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    main()

