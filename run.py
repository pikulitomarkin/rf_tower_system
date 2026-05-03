#!/usr/bin/env python3
"""
RF Tower System — Script de inicialização da aplicação Flask.

Uso:
    python run.py
    python run.py --host 127.0.0.1 --port 8080
    python run.py --debug
"""

import argparse
import importlib
import os
import sys


REQUIRED_MODULES = [
    ("flask", "Flask"),
    ("pandas", "pandas"),
    ("openpyxl", "openpyxl"),
    ("simplekml", "simplekml"),
    ("matplotlib", "matplotlib"),
    ("numpy", "numpy"),
    ("reportlab", "reportlab"),
    ("docx", "python-docx"),
    ("PIL", "pillow"),
    ("flask_cors", "flask-cors"),
]


def _check_imports():
    missing = []
    for mod_name, pkg_name in REQUIRED_MODULES:
        try:
            importlib.import_module(mod_name)
        except ImportError:
            missing.append(pkg_name)
    if missing:
        print(f"\n[ERRO] Dependências não instaladas: {', '.join(missing)}")
        print("Execute: pip install -r requirements.txt\n")
        sys.exit(1)
    print("[OK] Todas as dependências verificadas.")


def _ensure_directories(base_dir):
    dirs = ["uploads", "static/icons"]
    for d in dirs:
        path = os.path.join(base_dir, d)
        os.makedirs(path, exist_ok=True)
    print(f"[OK] Diretórios criados: {', '.join(dirs)}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="RF Tower System — Servidor Flask para simulação RF e geração KMZ"
    )
    parser.add_argument(
        "--host", default=os.environ.get("FLASK_HOST", "0.0.0.0"),
        help="Endereço de escuta (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("FLASK_PORT", 5000)),
        help="Porta de escuta (default: 5000)",
    )
    parser.add_argument(
        "--debug", action="store_true", default=os.environ.get("FLASK_DEBUG", "").lower() == "true",
        help="Ativa modo debug com hot-reload",
    )
    parser.add_argument(
        "--env", default=os.environ.get("FLASK_ENV", "development"),
        choices=["development", "production", "testing"],
        help="Ambiente de execução (default: development)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    print(f"\n{'='*55}")
    print("  RF Tower System — Sistema de Planejamento de Torres RF")
    print(f"{'='*55}\n")

    _check_imports()
    _ensure_directories(base_dir)

    from app import create_app
    app = create_app(args.env)

    print(f"\n[INFO] Iniciando servidor em http://{args.host}:{args.port}")
    print(f"[INFO] Ambiente: {args.env}  |  Debug: {args.debug}")
    print(f"[INFO] Interface web: http://{args.host}:{args.port}/")
    print(f"[INFO] API KMZ:        http://{args.host}:{args.port}/api/kmz/")
    print(f"[INFO] API RF:         http://{args.host}:{args.port}/api/rf/")
    print(f"[INFO] Template Excel: http://{args.host}:{args.port}/api/kmz/template")
    print(f"[INFO] Health check:   http://{args.host}:{args.port}/health")
    print(f"\nPressione Ctrl+C para encerrar.\n")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
