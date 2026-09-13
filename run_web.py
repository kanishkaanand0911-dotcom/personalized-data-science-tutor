"""Launch the learning-app frontend and its API.

    python run_web.py            # serves on http://127.0.0.1:8000
    python run_web.py --port 9000

The API is a thin wrapper around the existing backend in app/. It makes no
cleaning or modeling decisions of its own.
"""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes (dev)")
    args = parser.parse_args()

    uvicorn.run("web.api:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
