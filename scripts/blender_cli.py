#!/usr/bin/env python3
"""
Direct Live Foreground TCP Socket Bridge to Blender (`localhost:9876`) for `image-to-blender`.

How it works so the user watches every action happen live inside Blender (macOS & Windows):
1. Brings the Blender application window to the foreground (`bring_blender_to_front`)
   on both macOS (`osascript`) and Windows (`WScript.Shell.AppActivate('Blender')`).
2. Automatically injects `scripts/bpy_helpers.py` (`live_viewport_update`, `set_viewport_to_camera`)
   and triggers a live viewport swap (`bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)`)
   so the user watches every 3D object, modifier, material, and light appear step-by-step on screen.
"""

import argparse
import json
import platform
import socket
import subprocess
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


def bring_blender_to_front():
    """Bring the Blender application window to the foreground on macOS or Windows."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(
                ["osascript", "-e", 'tell application "Blender" to activate'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=4,
                check=False,
            )
        elif system == "Windows":
            ps_cmd = (
                "$wshell = New-Object -ComObject WScript.Shell; "
                "[void]$wshell.AppActivate('Blender')"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=4,
                check=False,
            )
    except Exception:
        pass


def send_command(
    cmd_type: str,
    params: dict = None,
    host: str = "localhost",
    port: int = 9876,
    timeout: float = 120.0,
    foreground: bool = True,
) -> dict:
    """Send a JSON command to the Blender MCP socket server and return the parsed response."""
    if not is_port_open(host, port):
        blender_bin = find_blender_executable()
        if blender_bin:
            uvx_bin = find_or_install_uvx()
            install_and_enable_blender_addon(blender_bin, uvx_bin)
            launch_blender_and_wait(blender_bin, port=port, timeout_sec=15)

    if foreground:
        bring_blender_to_front()

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
    parser = argparse.ArgumentParser(description="Direct Live Foreground CLI bridge to Blender MCP socket server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=9876)

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Check connection (auto-launches & focuses Blender) and enable Poly Haven")
    sub.add_parser("scene-info", help="Get current Blender scene summary")

    p_obj = sub.add_parser("object-info", help="Get detailed info for a specific Blender object")
    p_obj.add_argument("name", help="Object name in Blender")

    p_exec = sub.add_parser("exec", help="Execute Python code or .py script(s) live in the foreground inside Blender")
    p_exec.add_argument("-c", "--code", help="Inline Python code to run in Blender")
    p_exec.add_argument("-f", "--file", nargs="+", help="One or more .py files to run sequentially in Blender")

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
        res = send_command("ping", {}, host=args.host, port=args.port, foreground=True)
        send_command(
            "execute_code",
            {"code": "import bpy; bpy.context.scene.blendermcp_use_polyhaven = True"},
            host=args.host,
            port=args.port,
            foreground=False,
        )
        scene = send_command("get_scene_info", {}, host=args.host, port=args.port, foreground=False)
        print(json.dumps({"ping": res, "scene": scene}, indent=2))

    elif args.cmd == "scene-info":
        print(json.dumps(send_command("get_scene_info", {}, host=args.host, port=args.port, foreground=False), indent=2))

    elif args.cmd == "object-info":
        print(json.dumps(send_command("get_object_info", {"name": args.name}, host=args.host, port=args.port, foreground=False), indent=2))

    elif args.cmd == "exec":
        prelude = (
            "import sys\n"
            f"if r'''{str(SCRIPTS_DIR)}''' not in sys.path:\n"
            f"    sys.path.insert(0, r'''{str(SCRIPTS_DIR)}''')\n"
            "import bpy_helpers\n"
        )
        epilogue = "\nbpy_helpers.live_viewport_update(0.15)\n"

        if args.file:
            results = []
            bring_blender_to_front()
            for fpath in args.file:
                code_body = Path(fpath).read_text(encoding="utf-8")
                full_code = prelude + "\n" + code_body + epilogue
                r = send_command("execute_code", {"code": full_code}, host=args.host, port=args.port, foreground=False)
                results.append({"file": fpath, "result": r})
            print(json.dumps({"status": "success", "steps": results}, indent=2))
        else:
            user_code = args.code if args.code else sys.stdin.read()
            full_code = prelude + "\n" + user_code + epilogue
            print(json.dumps(send_command("execute_code", {"code": full_code}, host=args.host, port=args.port, foreground=True), indent=2))

    elif args.cmd == "screenshot":
        out_path = str(Path(args.output).resolve())
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        res = send_command(
            "get_viewport_screenshot",
            {"max_size": args.max_size, "filepath": out_path, "format": "png"},
            host=args.host,
            port=args.port,
            foreground=False,
        )
        print(json.dumps({"output_file": out_path, "response": res}, indent=2))

    elif args.cmd == "polyhaven-search":
        send_command(
            "execute_code",
            {"code": "import bpy; bpy.context.scene.blendermcp_use_polyhaven = True"},
            host=args.host,
            port=args.port,
            foreground=False,
        )
        params = {"asset_type": args.asset_type}
        if args.categories:
            params["categories"] = args.categories
        print(json.dumps(send_command("search_polyhaven_assets", params, host=args.host, port=args.port, foreground=False), indent=2))

    elif args.cmd == "polyhaven-download":
        send_command(
            "execute_code",
            {"code": "import bpy; bpy.context.scene.blendermcp_use_polyhaven = True"},
            host=args.host,
            port=args.port,
            foreground=True,
        )
        params = {
            "asset_id": args.asset_id,
            "asset_type": args.asset_type,
            "resolution": args.resolution,
        }
        if args.file_format:
            params["file_format"] = args.file_format
        print(json.dumps(send_command("download_polyhaven_asset", params, host=args.host, port=args.port, foreground=False), indent=2))


if __name__ == "__main__":
    main()
