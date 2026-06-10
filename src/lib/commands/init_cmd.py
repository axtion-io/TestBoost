# SPDX-License-Identifier: Apache-2.0
"""testboost init — project/session initialization."""

import argparse
import sys


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize .testboost/ in a project."""
    from pathlib import Path as _Path

    from src.lib.integrity import emit_token, get_or_create_secret
    from src.lib.plugins import get_registry
    from src.lib.session_tracker import create_session, init_project, set_session_technology

    project_path = args.project_path

    if not _Path(project_path).exists():
        print(f"Error: Project path does not exist: {project_path}", file=sys.stderr)
        return 1

    # --- Technology detection / selection (T016, T017, T018, T019) ---
    registry = get_registry()
    tech_arg = getattr(args, "tech", None)

    if tech_arg:
        # Explicit --tech override
        try:
            plugin = registry.get(tech_arg)
        except ValueError:
            available = [p["identifier"] for p in registry.list_plugins()]
            print(
                f"Error: Unknown technology '{tech_arg}'. "
                f"Available: {available}. "
                f"Run `testboost --list-plugins` to see all options.",
                file=sys.stderr,
            )
            return 1
        print(f"[+] Technology selected: {plugin.identifier}")
    else:
        # Auto-detect based on files present in project root
        plugin = registry.detect(_Path(project_path))
        if plugin is None:
            available = [p["identifier"] for p in registry.list_plugins()]
            print(
                "Error: Could not detect project technology. "
                f"No detection patterns matched. Available plugins: {available}. "
                "Use --tech <identifier> to specify explicitly.",
                file=sys.stderr,
            )
            return 1

        # Check if multiple plugins would match (T019)
        matched_plugins = [
            p for p in registry.list_plugins()
            if any((_Path(project_path) / pat).exists() for pat in p["detection_patterns"])
        ]
        if len(matched_plugins) > 1:
            others = [p["identifier"] for p in matched_plugins if p["identifier"] != plugin.identifier]
            print(
                f"[!] Multiple technology indicators found. Using: {plugin.identifier}. "
                f"Others: {others}. Override with --tech if needed."
            )
        else:
            matched_file = next(
                (pat for pat in plugin.detection_patterns if (_Path(project_path) / pat).exists()),
                plugin.detection_patterns[0],
            )
            print(f"[+] Technology detected: {plugin.identifier} (matched: {matched_file})")

    # Initialize directory structure
    result = init_project(project_path)
    print(f"[+] {result['message']}")

    # Ensure integrity secret exists
    get_or_create_secret(project_path)

    # Create initial session
    session = create_session(
        project_path,
        name=args.name if hasattr(args, "name") and args.name else None,
        description=args.description if hasattr(args, "description") and args.description else "",
    )
    print(f"[+] {session['message']}")
    print(f"    Session directory: {session['session_dir']}")
    print(f"    Session ID: {session['session_id']}")

    # Write technology to session metadata (T018)
    set_session_technology(_Path(session["session_dir"]), plugin.identifier)
    print(f"    Technology: {plugin.identifier}")

    emit_token(project_path, "init", session["session_id"])
    return 0
