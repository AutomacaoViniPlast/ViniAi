"""
Executado automaticamente pelo hook Stop do Claude Code.
Detecta mudancas na sessao, registra no vault Obsidian e injeta
resumo atualizado no CLAUDE.md para que a proxima sessao comece
com contexto completo sem precisar pedir nada.
"""

import re
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path("C:/Users/Martins/Documents/ViniAi")
VAULT = REPO / "project_memory" / "ViniAI-Memoria"
TEMP_DIR = VAULT / "Temp"
CHANGELOG = VAULT / "RunBooks" / "Changelog.md.md"
PENDENCIAS = VAULT / "RunBooks" / "Pendencias.md.md"
CLAUDE_MD = REPO / "CLAUDE.md"

# Marcadores da secao auto-gerada no CLAUDE.md
SECTION_START = "<!-- SYNC_MEMORY:START -->"
SECTION_END   = "<!-- SYNC_MEMORY:END -->"

# Mapeamento: padrao no path do arquivo -> nota do vault a revisar
WATCH_MAP = {
    "app/interpreter.py":      "[[Interpretacao-de-Intencao]]",
    "app/orchestrator.py":     "[[RAG-Conversacional]]",
    "app/agents.py":           "[[Agentes]]",
    "app/config.py":           "[[Agentes]] e [[SQLServer]]",
    "app/permissions.py":      "[[Claude-Code]] (permissoes)",
    "app/sql_service.py":      "[[SQLServer]]",
    "app/db.py":               "[[SQLServer]] e [[PostgreSQL]]",
    "app/llm_handler.py":      "[[RAG-Conversacional]]",
    "DocumentacaoProcessoDEV": "DocumentacaoProcessoDEV/",
}


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------

def get_changed_files():
    try:
        r1 = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=REPO
        )
        r2 = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True, text=True, cwd=REPO
        )
        files = set(r1.stdout.strip().splitlines() + r2.stdout.strip().splitlines())
        files = {f for f in files
                 if not f.startswith("project_memory/") and not f.startswith("scripts/")}
        return sorted(files)
    except Exception:
        return []


def get_last_commits(n=3):
    try:
        r = subprocess.run(
            ["git", "log", f"-{n}", "--pretty=format:%s (%ad)", "--date=short"],
            capture_output=True, text=True, cwd=REPO, encoding="utf-8", errors="replace"
        )
        return r.stdout.strip().splitlines()
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Vault
# ---------------------------------------------------------------------------

def get_vault_hints(changed_files):
    hints = set()
    for f in changed_files:
        for pattern, note in WATCH_MAP.items():
            if pattern in f:
                hints.add(note)
    return sorted(hints)


def read_pendencias_criticas():
    if not PENDENCIAS.exists():
        return []
    text = PENDENCIAS.read_text(encoding="utf-8")
    # Extrai linhas de tabela da secao "Criticas"
    criticas = []
    in_criticas = False
    for line in text.splitlines():
        if "## Críticas" in line or "## Criticas" in line:
            in_criticas = True
            continue
        if in_criticas and line.startswith("## "):
            break
        if in_criticas and line.startswith("| ") and "---" not in line and "Item" not in line:
            # Pega o primeiro campo da tabela (nome do item)
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if parts:
                criticas.append(parts[0])
    return criticas


def write_session_log(changed_files, hints):
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    filename = TEMP_DIR / f"sessao_{date_str}.md"

    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    lines = []
    if filename.exists():
        lines = filename.read_text(encoding="utf-8").splitlines()
        lines.append("")

    lines.append(f"## Sessao {time_str}")
    if changed_files:
        lines.append("\n**Arquivos alterados:**")
        for f in changed_files:
            lines.append(f"- `{f}`")
        if hints:
            lines.append("\n**Notas do vault para revisar:**")
            for h in hints:
                lines.append(f"- {h}")
    else:
        lines.append("Nenhuma alteracao de codigo nesta sessao.")

    filename.write_text("\n".join(lines), encoding="utf-8")
    return filename


def append_changelog(date_str, changed_files, hints):
    if not changed_files:
        return

    entry = f"\n## {date_str}\n"
    entry += "\n".join(f"- `{f}`" for f in changed_files)
    if hints:
        entry += "\n**Vault a atualizar:** " + ", ".join(hints)
    entry += "\n"

    if CHANGELOG.exists():
        existing = CHANGELOG.read_text(encoding="utf-8")
        if date_str in existing:
            return
        CHANGELOG.write_text(existing + entry, encoding="utf-8")
    else:
        CHANGELOG.write_text(
            "# Changelog de Sessoes\n\n"
            "> Gerado automaticamente pelo hook Stop do Claude Code.\n" + entry,
            encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Injecao no CLAUDE.md
# ---------------------------------------------------------------------------

def build_auto_section(changed_files, hints, commits, criticas):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        SECTION_START,
        "",
        "## Contexto Auto-Atualizado — Última Sessão",
        f"> Gerado em {now} por `scripts/sync_memory.py`",
        "",
    ]

    # Ultimos commits
    if commits:
        lines.append("**Ultimos commits:**")
        for c in commits:
            lines.append(f"- {c}")
        lines.append("")

    # Arquivos alterados na sessao atual
    if changed_files:
        lines.append("**Arquivos alterados nesta sessao:**")
        for f in changed_files:
            lines.append(f"- `{f}`")
        if hints:
            lines.append("")
            lines.append("**Notas do vault que precisam ser atualizadas:**")
            for h in hints:
                lines.append(f"- {h}")
        lines.append("")

    # Pendencias criticas
    if criticas:
        lines.append("**Pendencias criticas (de `RunBooks/Pendencias.md.md`):**")
        for p in criticas:
            lines.append(f"- {p}")
        lines.append("")

    lines.append(SECTION_END)
    return "\n".join(lines)


def update_claude_md(section_content):
    if not CLAUDE_MD.exists():
        return

    text = CLAUDE_MD.read_text(encoding="utf-8")

    if SECTION_START in text and SECTION_END in text:
        # Substitui secao existente
        pattern = re.compile(
            re.escape(SECTION_START) + r".*?" + re.escape(SECTION_END),
            re.DOTALL
        )
        new_text = pattern.sub(section_content, text)
    else:
        # Adiciona ao final
        new_text = text.rstrip() + "\n\n" + section_content + "\n"

    CLAUDE_MD.write_text(new_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    changed  = get_changed_files()
    hints    = get_vault_hints(changed)
    commits  = get_last_commits(3)
    criticas = read_pendencias_criticas()
    date_str = datetime.now().strftime("%Y-%m-%d")

    write_session_log(changed, hints)
    if changed:
        append_changelog(date_str, changed, hints)

    section = build_auto_section(changed, hints, commits, criticas)
    update_claude_md(section)

    if changed:
        print(f"[sync_memory] {len(changed)} arquivo(s) alterado(s).")
        if hints:
            print(f"[sync_memory] Vault para revisar: {', '.join(hints)}")
    else:
        print("[sync_memory] Nenhuma alteracao detectada.")

    print("[sync_memory] CLAUDE.md atualizado com contexto da sessao.")


if __name__ == "__main__":
    main()
