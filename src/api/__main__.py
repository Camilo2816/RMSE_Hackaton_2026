"""Servidor de la interfaz: python -m src.api --config configs/agentic.yaml --port 8000

Carga el pipeline una vez (en frío tarda: modelos a GPU) y sirve la API y la
interfaz en http://<host>:<port>/.
"""
from __future__ import annotations

import argparse
import logging
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="configs/agentic.yaml")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # consola de Windows (cp1252)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    import uvicorn

    from src.api.app import create_app
    from src.common.config import load_config

    print(f"cargando pipeline de {args.config}...", flush=True)
    app = create_app(load_config(args.config), config_path=args.config)
    print(f"interfaz en http://{args.host}:{args.port}/", flush=True)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
