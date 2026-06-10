# SPDX-License-Identifier: Apache-2.0
"""testboost resume + sign-answer — human-in-the-loop helpers."""

import argparse
import json
import sys
from pathlib import Path


def cmd_resume(args: argparse.Namespace) -> int:
    """Resume a paused session, or display its pending question.

    Without --answer-file: read the pending question.json and print it
      to stdout (markdown_preview). Exit 0 if a question is pending,
      1 if no session, 2 if no question is pending.

    With --answer-file: dispatch to the appropriate _cmd_<step>_async
      with the answer payload injected.
    """
    from src.lib.session_tracker import QUESTION_FILENAME, get_current_session

    project_path = args.project_path
    session = get_current_session(project_path)
    if not session:
        print("Error: No active session. Run `init` first.", file=sys.stderr)
        return 1

    session_dir = Path(session["session_dir"])
    qpath = session_dir / QUESTION_FILENAME
    answer_file = getattr(args, "answer_file", None)

    if not answer_file:
        if not qpath.exists():
            print("No question pending for this session.", file=sys.stderr)
            return 2
        question = json.loads(qpath.read_text(encoding="utf-8"))
        preview = question.get("markdown_preview") or json.dumps(question, indent=2)
        print(preview)
        return 0

    # Determine which step is awaiting and dispatch
    step = session.get("step", "")
    if not qpath.exists():
        print("Error: no pending question in this session.", file=sys.stderr)
        return 1
    question = json.loads(qpath.read_text(encoding="utf-8"))
    step = question.get("step", step)

    if step == "generation":
        # Replay the paused run's exact --files scope from the cursor, so
        # the recomputed target_files match and completed work is skipped.
        from src.lib.session_tracker import load_generation_cursor
        cursor = load_generation_cursor(str(session_dir))
        files_filter = cursor.get("files_filter") if cursor else None
        gen_args = argparse.Namespace(
            project_path=project_path,
            verbose=getattr(args, "verbose", False),
            files=files_filter,
            fail_on_uncertainty=True,
            answer_file=answer_file,
        )
        # Dispatch through the facade so test patches on src.lib.cli apply
        from src.lib import cli as _cli
        return _cli.cmd_generate(gen_args)

    if step == "validation":
        val_args = argparse.Namespace(
            project_path=project_path,
            verbose=getattr(args, "verbose", False),
            fail_on_uncertainty=True,
            answer_file=answer_file,
        )
        from src.lib import cli as _cli
        return _cli.cmd_validate(val_args)

    if step == "killer-tests":
        k_args = argparse.Namespace(
            project_path=project_path,
            verbose=getattr(args, "verbose", False),
            max_tests=10,
            fail_on_uncertainty=True,
            answer_file=answer_file,
        )
        from src.lib import cli as _cli
        return _cli.cmd_killer(k_args)

    print(f"Error: resume is not yet wired for step '{step}'.", file=sys.stderr)
    return 1
def cmd_sign_answer(args: argparse.Namespace) -> int:
    """Sign a raw answer payload so TestBoost will accept it on resume.

    Reads --question-file and --answer-file (raw, unsigned), produces a
    signed copy on stdout (or --output if provided).
    """
    from src.lib.integrity import sign_answer

    project_path = args.project_path
    qpath = Path(args.question_file)
    apath = Path(args.answer_file)

    if not qpath.exists():
        print(f"Error: question file not found: {qpath}", file=sys.stderr)
        return 1
    if not apath.exists():
        print(f"Error: answer file not found: {apath}", file=sys.stderr)
        return 1

    try:
        question = json.loads(qpath.read_text(encoding="utf-8"))
        raw_answer = json.loads(apath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: malformed JSON ({e})", file=sys.stderr)
        return 1

    if not isinstance(raw_answer, dict):
        print("Error: answer must be a JSON object at the top level", file=sys.stderr)
        return 1

    signed = sign_answer(raw_answer, question, project_path)
    out_json = json.dumps(signed, indent=2)

    output = getattr(args, "output", None)
    if output:
        Path(output).write_text(out_json, encoding="utf-8")
        print(f"Wrote signed answer to {output}")
    else:
        print(out_json)
    return 0
