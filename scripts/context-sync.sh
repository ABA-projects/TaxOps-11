#!/usr/bin/env bash
#
# context-sync.sh — Detección incremental de cambios para la coexistencia Claude + Kiro.
#
# Muestra qué cambió en el repo desde el último sync registrado, para que el agente
# (Claude o Kiro) reconstruya el contexto de forma incremental en lugar de releer todo.
#
# Uso:
#   scripts/context-sync.sh          # muestra el delta desde el último sync (no marca)
#   scripts/context-sync.sh --mark   # muestra el delta y actualiza el marcador de último sync
#
# El marcador se guarda en context/.last-sync (gitignorable). Prioriza incremental > completo.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${REPO_ROOT}" ]]; then
  echo "context-sync: no estás dentro de un repo git." >&2
  exit 1
fi
cd "${REPO_ROOT}"

MARK_FILE="context/.last-sync"
CURRENT_COMMIT="$(git rev-parse HEAD)"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

echo "=== TaxOps-11 · context-sync ==="
echo "Rama:   ${CURRENT_BRANCH}"
echo "HEAD:   ${CURRENT_COMMIT:0:12}"
echo

# --- Delta desde el último sync -------------------------------------------------
if [[ -f "${MARK_FILE}" ]]; then
  LAST_COMMIT="$(head -n1 "${MARK_FILE}" | tr -d '[:space:]')"
  if git cat-file -e "${LAST_COMMIT}^{commit}" 2>/dev/null; then
    if [[ "${LAST_COMMIT}" == "${CURRENT_COMMIT}" ]]; then
      echo "Sin commits nuevos desde el último sync (${LAST_COMMIT:0:12})."
    else
      echo "--- Commits desde el último sync (${LAST_COMMIT:0:12} .. HEAD) ---"
      git log --oneline "${LAST_COMMIT}..HEAD"
      echo
      echo "--- Archivos cambiados en ese rango ---"
      git diff --stat "${LAST_COMMIT}..HEAD"
    fi
  else
    echo "El marcador previo (${LAST_COMMIT:0:12}) ya no existe en el historial."
    echo "Mostrando los últimos 10 commits como referencia:"
    git log --oneline -10
  fi
else
  echo "Primer sync (no hay marcador previo)."
  echo "--- Últimos 10 commits ---"
  git log --oneline -10
fi

echo
# --- Cambios sin commitear (trabajo en curso) ----------------------------------
echo "--- Cambios sin commitear (working tree) ---"
if [[ -n "$(git status --porcelain)" ]]; then
  git status --short
else
  echo "(working tree limpio)"
fi

echo
# --- Recordatorio de contexto compartido ---------------------------------------
echo "--- Contexto compartido a revisar ---"
echo "  context/current-task.md   (tarea activa + próximos pasos)"
echo "  context/changelog.md      (últimas entradas)"
echo "  context/project-state.md  (estado por componente)"

# --- Marcar el sync si se pidió -------------------------------------------------
if [[ "${1:-}" == "--mark" ]]; then
  printf '%s\n' "${CURRENT_COMMIT}" > "${MARK_FILE}"
  echo
  echo "Marcador de último sync actualizado a ${CURRENT_COMMIT:0:12} (${MARK_FILE})."
fi
