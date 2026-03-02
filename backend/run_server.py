"""Entry point for the packaged backend server (used by PyInstaller)."""
import argparse
import uvicorn
from app.main import app


def main():
    parser = argparse.ArgumentParser(description="OHM Backend Server")
    parser.add_argument("--port", type=int, default=4243)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
