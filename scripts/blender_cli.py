#!/usr/bin/env python3
"""
Direct TCP Socket Bridge to Blender (`localhost:9876`) for `image-to-blender`.

Allows the AI agent to control Blender immediately (even before restarting the IDE
to reload `mcp_config.json`), and automatically launches Blender if port 9876 is not open.
Also injects `scripts/bpy_helpers.py` into Blender's Python path automatically.
"""

import argparse
import json
import socket
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from setup_blender_mcp import (  # noqa: E402
    find_blender_executable,
    find_or_install_uvx,
    install_and_enable_blender_addon,
    is_port_open,
    launch_blender_and_wait,
)


def send_command(cmd_type: str, params: dict = None, host: str = "localhost", port: int = 9876, timeout: float = 120.0) -> dict:
    """Send a JSON command to the Blender MCP socket server and return the parsed response."""
    if not is_port_open(host, port):
        blender_bin = find_blender_executable()
        if blender_bin:
            uvx_bin = find_or_install_uvx()
            install_and_enable_blender_addon(blender_bin, uvx_bin)
            launch_blender_and_wait(blender_bin, port=port, timeout_sec=15)

    if not is_port_open(host, port):
        return {
            "status": "error",
            "message": f"Blender MCP socket server is not reachable at {host}:{port}. Open Blender and ensure 'MCP for Blender' is running.",
        }

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect((host, port))
        payload = json.dumps({"type": cmd_type, "params": params or {}}).encode("utf-8")
        sock.sendall(payload)

        chunks = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                return json.loads(b"".join(chunks).decode("utf-8"))
            except json.JSONDecodeError:
                continue

    return {"status": "error", "message": "Connection closed before full JSON response was received."}


def main():
    parser = argparse.ArgumentParser(description="Direct CLI bridge to Blender MCP socket server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=9876)

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Check connection (auto-launches Blender if installed) and enable Poly Haven")
    sub.add_parser("scene-info", help="Get current Blender scene summary")

    p_obj = sub.add_parser("object-info", help="Get detailed info for a specific Blender object")
    p_obj.add_argument("name", help="Object name in Blender")

    p_exec = sub.add_parser("exec", help="Execute Python code or a .py script file inside Blender")
    p_exec.add_argument("-c", "--code", help="Inline Python code to run in Blender")
    p_exec.add_argument("-f", "--file", help="Path to a .py file to run in Blender")

    p_shot = sub.add_parser("screenshot", help="Capture 3D viewport screenshot to an image file")
    p_shot.add_argument("output", help="Output PNG file path")
    p_shot.add_argument("--max-size", type=int, default=1200, help="Max pixel dimension (default: 1200)")

    p_ph_search = sub.add_parser("polyhaven-search", help="Search Poly Haven assets (hdris, textures, models)")
    p_ph_search.add_argument("asset_type", choices=["hdris", "textures", "models", "all"])
    p_ph_search.add_argument("--categories", default="", help="Optional comma-separated categories")

    p_ph_dl = sub.add_parser("polyhaven-download", help="Download and import a Poly Haven asset into Blender")
    p_ph_dl.add_argument("asset_id", help="Asset ID from search")
    p_ph_dl.add_argument("asset_type", choices=["hdris", "textures", "models"])
    p_ph_dl.add_argument("--resolution", default="1k", help="Resolution (1k, 2k, 4k)")
    p_ph_dl.add_argument("--file-format", default=None, help="Optional format (hdr, exr, jpg, png, gltf, blend)")

    args = parser.parse_args()

    if args.cmd == "status":
        res = send_command("ping", {}, host=args.host, port=args.port)
        # Ensure Poly Haven is enabled automatically
        send_command(
            "execute_code",
            {"code": "import bpy; bpy.context.scene.blendermcp_use_polyhaven = True"},
            host=args.host,
            port=args.port,
        )
        scene = send_command("get_scene_info", {}, host=args.host, port=args.port)
        print(json.dumps({"ping": res, "scene": scene}, indent=2))

    elif args.cmd == "scene-info":
        print(json.dumps(send_command("get_scene_info", {}, host=args.host, port=args.port), indent=2))

    elif args.cmd == "object-info":
        print(json.dumps(send_command("get_object_info", {"name": args.name}, host=args.host, port=args.port), indent=2))

    elif args.cmd == "exec":
        user_code = ""
        if args.file:
            user_code = Path(args.file).read_text(encoding="utf-8")
        elif args.code:
            user_code = args.code
        else:
            user_code = sys.stdin.read()

        # Prepend sys.path injection so `import bpy_helpers` works automatically inside Blender
        prelude = (
            "import sys\n"
            f"if r'''{str(SCRIPTS_DIR)}''' not in sys.path:\n"
            f"    sys.path.insert(0, r'''{str(SCRIPTS_DIR)}''')\n"
        )
        full_code = prelude + "\n" + user_code
        print(json.dumps(send_command("execute_code", {"code": full_code}, host=args.host, port=args.port), indent=2))

    elif args.cmd == "screenshot":
        out_path = str(Path(args.output).resolve())
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        res = send_command(
            "get_viewport_screenshot",
            {"max_size": args.max_size, "filepath": out_path, "format": "png"},
            host=args.host,
            port=args.port,
        )
        print(json.dumps({"output_file": out_path, "response": res}, indent=2))

    elif args.cmd == "polyhaven-search":
        # Make sure Poly Haven is enabled first
        send_command(
            "execute_code",
            {"code": "import bpy; bpy.context.scene.blendermcp_use_polyhaven = True"},
            host=args.host,
            port=args.port,
        )
        params = {"asset_type": args.asset_type}
        if args.categories:
            params["categories"] = args.categories
        print(json.dumps(send_command("search_polyhaven_assets", params, host=args.host, port=args.port), indent=2))

    elif args.cmd == "polyhaven-download":
        send_command(
            "execute_code",
            {"code": "import bpy; bpy.context.scene.blendermcp_use_polyhaven = True"},
            host=args.host,
            port=args.port,
        )
        params = {
            "asset_id": args.asset_id,
            "asset_type": args.asset_type,
            "resolution": args.resolution,
        }
        if args.file_format:
            params["file_format"] = args.file_format
        print(json.dumps(send_command("download_polyhaven_asset", params, host=args.host, port=args.port), indent=2))


if __name__ == "__main__":
    main()
