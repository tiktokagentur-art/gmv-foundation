#!/usr/bin/env bash
# Gemeinsame bwrap-Argumente für Symphony auf dem Pilot-Host (ENG-003).
# Ohne Root: bwrap mit unprivilegierten User-Namespaces.
# Wird von run-symphony.sh und sandbox-selftest.sh per `source` geladen.
#
# Modell: Das ganze Dateisystem bleibt sichtbar (Binärdateien, Toolchains),
# Credential-Speicher werden mit leerem tmpfs bzw. /dev/null überdeckt.
# Ausnahme: ~/.codex/auth.json bleibt für den Modellzugriff von Codex
# erreichbar (Restrisiko, siehe docs/symphony/sandbox.md).

: "${PILOT_DIR:=/workspace/symphony-pilot}"
: "${GMV_HOME:=/home/box}"

gmv_bwrap_args() {
  local args=(
    --die-with-parent
    --new-session
    --dev-bind / /
    --proc /proc
    --tmpfs /tmp
  )
  local mask_dirs=(
    "$GMV_HOME/secrets"
    "$GMV_HOME/.config/gh"
    "$GMV_HOME/.config/google-chrome"
    "$GMV_HOME/.cursor"
    "$GMV_HOME/agent-data"
    "$GMV_HOME/sand-data"
    "$GMV_HOME/chrome-profile"
    "$GMV_HOME/cli-config"
    "$GMV_HOME/Downloads"
    /cursor
  )
  local d seen=" "
  for d in "${mask_dirs[@]}"; do
    [ -d "$d" ] || continue
    d=$(readlink -f "$d")  # bwrap kann nicht auf Symlinks mounten
    case "$seen" in *" $d "*) continue ;; esac
    seen+="$d "
    args+=(--tmpfs "$d")
  done
  local mask_files=(
    "$GMV_HOME/.gitconfig"
    "$GMV_HOME/.git-credentials"
    "$GMV_HOME/.netrc"
    "$GMV_HOME/.sand-onepassword-extension-enabled"
  )
  local f
  for f in "${mask_files[@]}"; do
    [ -e "$f" ] && args+=(--ro-bind /dev/null "$(readlink -f "$f")")
  done
  # /workspace: nur das Pilot-Verzeichnis bleibt sichtbar.
  args+=(--tmpfs /workspace --bind "$PILOT_DIR" "$PILOT_DIR")
  # ~/.codex: leer und beschreibbar (sitzungslokal), nur auth.json eingeblendet.
  args+=(--tmpfs "$GMV_HOME/.codex")
  if [ -f "$GMV_HOME/.codex/auth.json" ]; then
    args+=(--bind "$GMV_HOME/.codex/auth.json" "$GMV_HOME/.codex/auth.json")
  fi
  printf '%s\0' "${args[@]}"
}
