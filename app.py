"""
Open 3D Creator — FastAPI hosts Direct3D-S2, PIXEstL, and pcb2print3d APIs + static Win32-style UI.

Run: python app.py
Then open http://127.0.0.1:7860/
"""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Open 3D Creator web server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    uvicorn.run(
        "backend.server:app",
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
