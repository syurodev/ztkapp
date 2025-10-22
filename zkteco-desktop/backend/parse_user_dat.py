#!/usr/bin/env python3
"""
Simple service to parse a ZKTeco-style user.dat file uploaded by a client.

Usage:
    python parse_user_dat.py serve --host 0.0.0.0 --port 5050

Then POST a multipart/form-data request to /upload with a `file` field.

You can also parse a file directly:
    python parse_user_dat.py parse --input user.dat --output users.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable, List, Tuple, TypedDict

from flask import Flask, jsonify, request


class ParsedUser(TypedDict):
    employee_name: str
    employee_code: str


# Regex to capture name + numeric code. Names in these files are typically
# uppercase ASCII, but we allow spaces and hyphen/underscore as defensive measure.
NAME_CODE_REGEX = re.compile(r"([A-Z0-9 _.-]+?)\s+(\d{4,})")


def _clean_text(raw_bytes: bytes) -> str:
    """
    Decode the raw bytes (ASCII fallback) and strip control characters that may
    appear in the proprietary file format.
    """
    text = raw_bytes.decode("ascii", errors="ignore")
    return re.sub(r"[^\x20-\x7E\s]", " ", text)


def _parse_matches(matches: Iterable[Tuple[str, str]]) -> List[ParsedUser]:
    """
    Convert regex matches to structured entries while skipping ADMIN users.
    """
    parsed: List[ParsedUser] = []
    for name, code in matches:
        cleaned_name = name.strip()
        cleaned_code = code.strip()

        if not cleaned_name or cleaned_name.upper() == "ADMIN":
            continue

        parsed.append(
            ParsedUser(
                employee_name=cleaned_name,
                employee_code=cleaned_code,
            )
        )
    return parsed


def parse_user_dat(raw_bytes: bytes) -> List[ParsedUser]:
    cleaned_text = _clean_text(raw_bytes)
    matches = NAME_CODE_REGEX.findall(cleaned_text)
    return _parse_matches(matches)


# ------------------------------------------------------------------------------
# CLI helpers
# ------------------------------------------------------------------------------
def _cmd_parse(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    data = input_path.read_bytes()
    parsed = parse_user_dat(data)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Parsed {len(parsed)} records -> {output_path}")
    else:
        # Emit to stdout
        print(json.dumps(parsed, indent=2, ensure_ascii=False))


def _create_app() -> Flask:
    flask_app = Flask(__name__)

    @flask_app.post("/upload")
    def upload_dat():
        if "file" not in request.files:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Missing `file` in form-data payload.",
                    }
                ),
                400,
            )

        file_storage = request.files["file"]
        file_bytes = file_storage.read()
        if not file_bytes:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Uploaded file is empty.",
                    }
                ),
                400,
            )

        parsed = parse_user_dat(file_bytes)
        return jsonify(
            {
                "success": True,
                "total": len(parsed),
                "data": parsed,
            }
        )

    return flask_app


def _cmd_serve(args: argparse.Namespace) -> None:
    app = _create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse ZKTeco user.dat files into JSON."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser(
        "parse", help="Parse a local .dat file and emit JSON"
    )
    parse_parser.add_argument("--input", required=True, help="Path to user.dat file")
    parse_parser.add_argument(
        "--output", help="Optional output path for JSON (defaults to stdout)"
    )
    parse_parser.set_defaults(func=_cmd_parse)

    serve_parser = subparsers.add_parser(
        "serve", help="Run a small Flask server to accept uploads"
    )
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=5050)
    serve_parser.add_argument(
        "--debug", action="store_true", help="Enable Flask debug mode"
    )
    serve_parser.set_defaults(func=_cmd_serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
