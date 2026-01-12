#!/usr/bin/env python3
"""
Script pour détecter les HTTPException et autres erreurs non loggées dans le code.

Usage:
    python scripts/detect_unlogged_exceptions.py
    python scripts/detect_unlogged_exceptions.py --check-only  # Exit 1 si des problèmes trouvés
"""

import re
import sys
from pathlib import Path
from typing import NamedTuple


class UnloggedError(NamedTuple):
    """Représente une erreur non loggée détectée."""

    file_path: Path
    line_number: int
    error_type: str
    code_snippet: str
    severity: str  # "critical", "important", "minor"


def detect_httpexception_without_log(src_dir: Path) -> list[UnloggedError]:
    """
    Détecte les raise HTTPException qui ne sont pas précédées d'un logger.xxx().

    Args:
        src_dir: Répertoire source à analyser

    Returns:
        Liste des erreurs non loggées détectées
    """
    errors: list[UnloggedError] = []
    api_files = list((src_dir / "api").rglob("*.py"))

    for file_path in api_files:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        for i, line in enumerate(lines, start=1):
            # Détecter raise HTTPException
            if "raise HTTPException" in line:
                # Vérifier les 5 lignes précédentes pour un logger.xxx()
                has_log_before = False
                context_start = max(0, i - 6)

                for prev_line in lines[context_start : i - 1]:
                    if re.search(r"logger\.(error|warning|info|debug)", prev_line):
                        has_log_before = True
                        break

                if not has_log_before:
                    # Extraire le code_snippet (ligne actuelle + 2 suivantes)
                    snippet_lines = lines[i - 1 : min(i + 2, len(lines))]
                    snippet = "\n".join(snippet_lines)

                    # Déterminer la sévérité selon le status code
                    severity = "important"
                    if "status_code=404" in line or "status_code=400" in line or "status_code=500" in line:
                        severity = "critical"

                    errors.append(
                        UnloggedError(
                            file_path=file_path,
                            line_number=i,
                            error_type="HTTPException",
                            code_snippet=snippet,
                            severity=severity,
                        )
                    )

    return errors


def detect_validation_errors_without_log(src_dir: Path) -> list[UnloggedError]:
    """
    Détecte les raise ValidationError qui ne sont pas loggées.

    Args:
        src_dir: Répertoire source à analyser

    Returns:
        Liste des erreurs non loggées détectées
    """
    errors: list[UnloggedError] = []
    all_files = list(src_dir.rglob("*.py"))

    for file_path in all_files:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        for i, line in enumerate(lines, start=1):
            # Détecter raise ValidationError (custom)
            if re.search(r"raise\s+ValidationError\(", line):
                # Vérifier les 3 lignes précédentes
                has_log_before = False
                context_start = max(0, i - 4)

                for prev_line in lines[context_start : i - 1]:
                    if re.search(r"logger\.(error|warning)", prev_line):
                        has_log_before = True
                        break

                if not has_log_before:
                    snippet_lines = lines[i - 1 : min(i + 2, len(lines))]
                    snippet = "\n".join(snippet_lines)

                    errors.append(
                        UnloggedError(
                            file_path=file_path,
                            line_number=i,
                            error_type="ValidationError",
                            code_snippet=snippet,
                            severity="important",
                        )
                    )

    return errors


def detect_silent_except_pass(src_dir: Path) -> list[UnloggedError]:
    """
    Détecte les blocs except: pass qui avalent silencieusement les erreurs.

    Args:
        src_dir: Répertoire source à analyser

    Returns:
        Liste des erreurs silencieuses détectées
    """
    errors: list[UnloggedError] = []
    all_files = list(src_dir.rglob("*.py"))

    for file_path in all_files:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        for i, line in enumerate(lines, start=1):
            # Détecter except.*: suivi de pass
            if re.search(r"except\s+.*:\s*$", line):
                # Vérifier la ligne suivante
                if i < len(lines):
                    next_line = lines[i].strip()
                    if next_line == "pass":
                        snippet_lines = lines[i - 1 : min(i + 2, len(lines))]
                        snippet = "\n".join(snippet_lines)

                        errors.append(
                            UnloggedError(
                                file_path=file_path,
                                line_number=i,
                                error_type="except_pass",
                                code_snippet=snippet,
                                severity="critical",
                            )
                        )

    return errors


def print_report(errors: list[UnloggedError], verbose: bool = True) -> None:
    """
    Affiche un rapport des erreurs détectées.

    Args:
        errors: Liste des erreurs détectées
        verbose: Afficher les snippets de code
    """
    if not errors:
        print("✅ Aucune erreur non loggée détectée!")
        return

    # Grouper par sévérité
    critical = [e for e in errors if e.severity == "critical"]
    important = [e for e in errors if e.severity == "important"]
    minor = [e for e in errors if e.severity == "minor"]

    print(f"\n{'=' * 80}")
    print(f"🔍 RAPPORT: {len(errors)} erreurs non loggées détectées")
    print(f"{'=' * 80}\n")

    print(f"🔴 Critiques: {len(critical)}")
    print(f"🟠 Importantes: {len(important)}")
    print(f"🟡 Mineures: {len(minor)}\n")

    # Afficher par sévérité
    for severity, emoji in [("critical", "🔴"), ("important", "🟠"), ("minor", "🟡")]:
        severity_errors = [e for e in errors if e.severity == severity]
        if not severity_errors:
            continue

        print(f"\n{emoji} {severity.upper()} ({len(severity_errors)})")
        print("-" * 80)

        for error in severity_errors:
            relative_path = error.file_path.relative_to(Path.cwd())
            print(f"\n📁 {relative_path}:{error.line_number}")
            print(f"   Type: {error.error_type}")

            if verbose:
                print("   Code:")
                for line in error.code_snippet.split("\n"):
                    print(f"      {line}")

    print(f"\n{'=' * 80}\n")


def main() -> int:
    """
    Point d'entrée principal.

    Returns:
        0 si aucun problème, 1 si des problèmes détectés
    """
    # Fix Windows console encoding
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

    check_only = "--check-only" in sys.argv
    verbose = "--verbose" in sys.argv or not check_only

    src_dir = Path(__file__).parent.parent / "src"

    if not src_dir.exists():
        print(f"❌ Répertoire source introuvable: {src_dir}")
        return 1

    print("🔍 Analyse du code pour détecter les erreurs non loggées...")
    print(f"📂 Répertoire: {src_dir}\n")

    # Détecter les différents types d'erreurs
    all_errors: list[UnloggedError] = []

    print("- Recherche des HTTPException non loggées...")
    all_errors.extend(detect_httpexception_without_log(src_dir))

    print("- Recherche des ValidationError non loggées...")
    all_errors.extend(detect_validation_errors_without_log(src_dir))

    print("- Recherche des except: pass silencieux...")
    all_errors.extend(detect_silent_except_pass(src_dir))

    # Afficher le rapport
    print_report(all_errors, verbose=verbose)

    # Statistiques par fichier
    if all_errors and verbose:
        files_with_errors = {}
        for error in all_errors:
            relative_path = str(error.file_path.relative_to(Path.cwd()))
            files_with_errors[relative_path] = files_with_errors.get(relative_path, 0) + 1

        print("📊 Fichiers les plus problématiques:")
        sorted_files = sorted(files_with_errors.items(), key=lambda x: x[1], reverse=True)
        for file_path, count in sorted_files[:10]:
            print(f"   {count:3d} - {file_path}")
        print()

    # Exit code
    if check_only and all_errors:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
