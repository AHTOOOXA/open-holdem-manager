"""Entry point for the packaged backend server (used by PyInstaller)."""
import argparse
import uvicorn
from app.main import app


def self_check():
    """Exit non-zero if all-in EV can't be computed (e.g. PyInstaller missed eval7's deps)
    or psycopg2 (tracker import, imported lazily) is missing from the build."""
    from app.equity import calculate_headsup_equity
    import psycopg2  # noqa: F401  (raises ImportError -> non-zero exit)
    from psycopg2 import extensions  # noqa: F401  (the compiled _psycopg module)

    equity = calculate_headsup_equity(("Ah", "Ad"), ("Kh", "Kd"), ["2c", "7d", "9s"])
    if not 0.85 < equity < 0.95:
        raise SystemExit(f"self-check failed: AA vs KK equity {equity}")
    print(f"self-check ok (AA vs KK on 2c7d9s: {equity:.3f}; psycopg2 {psycopg2.__version__})")


def main():
    parser = argparse.ArgumentParser(description="OHM Backend Server")
    parser.add_argument("--port", type=int, default=4243)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument(
        "--self-check", action="store_true",
        help="Check that optional native deps work in this build, then exit",
    )
    args = parser.parse_args()

    if args.self_check:
        self_check()
        return

    config = uvicorn.Config(
        app, host=args.host, port=args.port, log_level="info",
        # Don't let an open request (e.g. an import stream) hold up quitting;
        # Electron kills the process after ~15s anyway.
        timeout_graceful_shutdown=5,
    )
    server = uvicorn.Server(config)
    # POST /api/shutdown sets server.should_exit for a clean exit
    app.state.server = server
    server.run()


if __name__ == "__main__":
    main()
