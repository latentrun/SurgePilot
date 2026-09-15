#!/bin/sh
set -eu
umask 077

RELEASE_VERSION="@@RELEASE_VERSION@@"
REPOSITORY="latentrun/SurgePilot"
ARCHIVE_NAME="surgepilot-${RELEASE_VERSION}.tar.gz"
SIDECAR_NAME="${ARCHIVE_NAME}.sha256"
DEFAULT_RELEASE_BASE_URL="https://github.com/${REPOSITORY}/releases/download/${RELEASE_VERSION}"
RELEASE_BASE_URL=${SURGEPILOT_INSTALLER_RELEASE_BASE_URL:-$DEFAULT_RELEASE_BASE_URL}

WORK_DIR=
LAUNCHER_TEMP=
PUBLISHED_ROOT=

fail() {
    printf 'SurgePilot installer: %s\n' "$*" >&2
    exit 1
}

cleanup() {
    if [ -n "$PUBLISHED_ROOT" ]; then
        rm -f "$LAUNCHER"
        rm -rf "$PUBLISHED_ROOT"
    fi
    if [ -n "$LAUNCHER_TEMP" ]; then
        rm -f "$LAUNCHER_TEMP"
    fi
    if [ -n "$WORK_DIR" ]; then
        rm -rf "$WORK_DIR"
    fi
}

trap cleanup 0
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "$1 is required."
}

download() {
    source_url=$1
    destination=$2
    if [ "${SURGEPILOT_INSTALLER_RELEASE_BASE_URL+x}" = x ]; then
        curl -fsSL "$source_url" -o "$destination" || \
            fail "Download failed for ${source_url##*/}."
    else
        curl --proto '=https' --tlsv1.2 -fsSL "$source_url" -o "$destination" || \
            fail "Download failed for ${source_url##*/}."
    fi
}

calculate_sha256() {
    case "$OPERATING_SYSTEM" in
        Linux) sha256sum "$1" | { IFS=' ' read -r digest rest; printf '%s\n' "$digest"; } ;;
        Darwin) shasum -a 256 "$1" | { IFS=' ' read -r digest rest; printf '%s\n' "$digest"; } ;;
    esac
}

validate_payload() {
    payload=$1
    for required in \
        surgepilot \
        compose/docker-compose.yml \
        .env.example \
        VERSION \
        README.md \
        release-manifest.json \
        scripts/__init__.py \
        scripts/bootstrap_deployment_env.py \
        scripts/fetch_runtime_release.py \
        scripts/release_preflight.py \
        compose/grafana/dashboards/surgepilot-jmeter-13644.json \
        compose/grafana/entrypoint.sh \
        compose/grafana/provisioning/dashboards/surgepilot.yml \
        compose/grafana/provisioning/datasources/influxdb.yml \
        compose/minio/init-bucket.sh \
        compose/nginx/default.conf
    do
        [ -f "$payload/$required" ] && [ ! -L "$payload/$required" ] || \
            fail "Required release file is missing or non-regular: $required"
    done
    [ -x "$payload/surgepilot" ] || fail "Required release file is not executable: surgepilot"
    [ "$(cat "$payload/VERSION")" = "$RELEASE_VERSION" ] || \
        fail "Release version marker does not match $RELEASE_VERSION."
    manifest_version_lines=$( \
        grep -E '"version"[[:space:]]*:' "$payload/release-manifest.json" || : \
    )
    [ "$manifest_version_lines" = '  "version": "'"$RELEASE_VERSION"'"' ] || \
        fail "Release manifest version does not match $RELEASE_VERSION."
}

validate_archive() {
    archive=$1
    if tar -tvzf "$archive" | grep -E '^[^-d]' >/dev/null 2>&1; then
        fail "Release archive contains an unsupported member type."
    fi
    archive_members=$(tar -tzf "$archive" | LC_ALL=C sort)
    expected_members=$(cat <<'EOF'
surgepilot/
surgepilot/.env.example
surgepilot/README.md
surgepilot/VERSION
surgepilot/compose/
surgepilot/compose/docker-compose.yml
surgepilot/compose/grafana/
surgepilot/compose/grafana/dashboards/
surgepilot/compose/grafana/dashboards/surgepilot-jmeter-13644.json
surgepilot/compose/grafana/entrypoint.sh
surgepilot/compose/grafana/provisioning/
surgepilot/compose/grafana/provisioning/dashboards/
surgepilot/compose/grafana/provisioning/dashboards/surgepilot.yml
surgepilot/compose/grafana/provisioning/datasources/
surgepilot/compose/grafana/provisioning/datasources/influxdb.yml
surgepilot/compose/minio/
surgepilot/compose/minio/init-bucket.sh
surgepilot/compose/nginx/
surgepilot/compose/nginx/default.conf
surgepilot/release-manifest.json
surgepilot/scripts/
surgepilot/scripts/__init__.py
surgepilot/scripts/bootstrap_deployment_env.py
surgepilot/scripts/fetch_runtime_release.py
surgepilot/scripts/release_preflight.py
surgepilot/surgepilot
EOF
)
    [ "$archive_members" = "$expected_members" ] || \
        fail "Release archive contains unexpected or missing members."
}

shell_quote() {
    escaped=$(printf '%s' "$1" | sed "s/'/'\\\\''/g")
    printf "'%s'" "$escaped"
}

publish_installation() {
    payload=$1
    quoted_install_root=$(shell_quote "$INSTALL_ROOT")
    LAUNCHER_TEMP=$(mktemp "$LAUNCHER_PARENT/.surgepilot-launcher.XXXXXX") || \
        fail "Cannot prepare the launcher."
    cat > "$LAUNCHER_TEMP" <<EOF
#!/bin/sh
set -eu
SURGEPILOT_COMMAND_NAME=surgepilot
export SURGEPILOT_COMMAND_NAME
INSTALL_ROOT=$quoted_install_root
exec "\$INSTALL_ROOT/surgepilot" "\$@"
EOF
    chmod 700 "$LAUNCHER_TEMP" || fail "Cannot make the launcher executable."

    [ ! -e "$INSTALL_ROOT" ] && [ ! -L "$INSTALL_ROOT" ] || \
        fail "Installation root already exists: $INSTALL_ROOT"
    [ ! -e "$LAUNCHER" ] && [ ! -L "$LAUNCHER" ] || \
        fail "Launcher already exists: $LAUNCHER"

    trap '' HUP INT TERM
    mv "$payload" "$INSTALL_ROOT" || fail "Cannot publish the installation root."
    PUBLISHED_ROOT=$INSTALL_ROOT
    if ! mv "$LAUNCHER_TEMP" "$LAUNCHER"; then
        rm -f "$LAUNCHER_TEMP"
        LAUNCHER_TEMP=
        rm -rf "$PUBLISHED_ROOT"
        PUBLISHED_ROOT=
        fail "Cannot publish the launcher."
    fi
    LAUNCHER_TEMP=
    PUBLISHED_ROOT=
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM
}

case ${HOME:-} in
    /*) ;;
    '') fail "HOME is required." ;;
    *) fail "HOME must be an absolute path." ;;
esac
case ${XDG_DATA_HOME:-} in
    '') DATA_HOME="$HOME/.local/share" ;;
    /*) DATA_HOME=$XDG_DATA_HOME ;;
    *) fail "XDG_DATA_HOME must be an absolute path." ;;
esac

INSTALL_ROOT="$DATA_HOME/surgepilot"
INSTALL_PARENT=${INSTALL_ROOT%/*}
LAUNCHER="$HOME/.local/bin/surgepilot"
LAUNCHER_PARENT=${LAUNCHER%/*}

for command_name in cat curl tar mktemp mkdir rm mv chmod grep sed sort uname
do
    require_command "$command_name"
done

OPERATING_SYSTEM=$(uname -s)
case "$OPERATING_SYSTEM" in
    Linux) require_command sha256sum ;;
    Darwin) require_command shasum ;;
    *) fail "Unsupported operating system: $OPERATING_SYSTEM" ;;
esac

[ ! -e "$INSTALL_ROOT" ] && [ ! -L "$INSTALL_ROOT" ] || \
    fail "Installation root already exists: $INSTALL_ROOT"
[ ! -e "$LAUNCHER" ] && [ ! -L "$LAUNCHER" ] || \
    fail "Launcher already exists: $LAUNCHER"

mkdir -p "$INSTALL_PARENT" "$LAUNCHER_PARENT" || fail "Cannot create user installation paths."
WORK_DIR=$(mktemp -d "$INSTALL_PARENT/.surgepilot-install.XXXXXX") || \
    fail "Cannot prepare private installation state."
ARCHIVE="$WORK_DIR/$ARCHIVE_NAME"
SIDECAR="$WORK_DIR/$SIDECAR_NAME"

download "$RELEASE_BASE_URL/$ARCHIVE_NAME" "$ARCHIVE"
download "$RELEASE_BASE_URL/$SIDECAR_NAME" "$SIDECAR"

IFS=' ' read -r expected_digest recorded_name extra < "$SIDECAR" || \
    fail "Checksum sidecar is invalid."
case "$expected_digest" in
    *[!0-9a-f]*|'') fail "Checksum sidecar is invalid." ;;
esac
[ "${#expected_digest}" -eq 64 ] || fail "Checksum sidecar is invalid."
[ "$recorded_name" = "$ARCHIVE_NAME" ] && [ -z "${extra:-}" ] || \
    fail "Checksum sidecar names an unexpected archive."
actual_digest=$(calculate_sha256 "$ARCHIVE")
[ "$actual_digest" = "$expected_digest" ] || fail "Bundle checksum verification failed."
validate_archive "$ARCHIVE"

EXTRACT_ROOT="$WORK_DIR/extracted"
mkdir "$EXTRACT_ROOT" || fail "Cannot prepare extracted release state."
tar -xzf "$ARCHIVE" -C "$EXTRACT_ROOT" || fail "Bundle extraction failed."
PAYLOAD="$EXTRACT_ROOT/surgepilot"
validate_payload "$PAYLOAD"
publish_installation "$PAYLOAD"

printf 'SurgePilot %s installed in %s\n' "$RELEASE_VERSION" "$INSTALL_ROOT"
printf 'Launcher: %s\n' "$LAUNCHER"
printf 'Run surgepilot up from an interactive terminal.\n'
case ":${PATH:-}:" in
    *":$LAUNCHER_PARENT:"*) ;;
    *)
        printf 'If surgepilot is not found, run %s up or add it for this shell:\n' "$LAUNCHER"
        printf '  export PATH="%s:$PATH"\n' "$LAUNCHER_PARENT"
        ;;
esac
