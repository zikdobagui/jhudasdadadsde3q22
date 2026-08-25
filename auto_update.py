import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REMOTE = os.getenv("AUTO_GIT_REMOTE", "origin")
BRANCH = os.getenv("AUTO_GIT_BRANCH", "main")


def run_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def log(message: str) -> None:
    print(f"[auto-update] {message}", flush=True)


def has_git_repo() -> bool:
    result = run_git("rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def has_local_changes() -> bool:
    result = run_git("status", "--porcelain")
    if result.returncode != 0:
        log(f"Nao foi possivel checar alteracoes locais:\n{result.stdout.strip()}")
        return True
    return bool(result.stdout.strip())


def update() -> bool:
    if os.getenv("AUTO_GIT_UPDATE", "1").lower() in {"0", "false", "no", "off"}:
        log("Atualizacao automatica desativada por AUTO_GIT_UPDATE.")
        return False

    if not has_git_repo():
        log("Este ambiente nao tem repositorio Git; iniciando sem atualizar.")
        return False

    if has_local_changes():
        log("Existem alteracoes locais rastreadas; pulei o git pull para nao sobrescrever dados.")
        return False

    log(f"Buscando atualizacoes de {REMOTE}/{BRANCH}...")
    fetch = run_git("fetch", REMOTE, BRANCH)
    if fetch.returncode != 0:
        log(f"Falha no git fetch:\n{fetch.stdout.strip()}")
        return False

    local = run_git("rev-parse", "HEAD")
    upstream = run_git("rev-parse", f"{REMOTE}/{BRANCH}")
    if local.returncode != 0 or upstream.returncode != 0:
        log("Nao foi possivel comparar a versao local com a remota.")
        return False

    if local.stdout.strip() == upstream.stdout.strip():
        log("Ja esta atualizado.")
        return False

    pull = run_git("pull", "--ff-only", REMOTE, BRANCH)
    if pull.returncode != 0:
        log(f"Falha no git pull:\n{pull.stdout.strip()}")
        return False

    log("Atualizacao aplicada com sucesso.")
    return True


if __name__ == "__main__":
    try:
        sys.exit(0 if update() else 1)
    except Exception as exc:
        log(f"Erro inesperado: {exc}")
        sys.exit(1)
