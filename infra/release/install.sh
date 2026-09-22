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
OWNER_CANDIDATE=
LOCK_OWNED=false
LOCK_NONCE=
STAGED_RELEASE=

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
    if [ -n "$STAGED_RELEASE" ]; then
        rm -rf "$STAGED_RELEASE"
    fi
    if [ -n "$OWNER_CANDIDATE" ]; then
        rm -f "$OWNER_CANDIDATE"
    fi
    release_lock
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
        surgepilot-dispatcher \
        compose/docker-compose.yml \
        .env.example \
        VERSION \
        README.md \
        release-manifest.json \
        scripts/__init__.py \
        scripts/bootstrap_deployment_env.py \
        scripts/fetch_runtime_release.py \
        scripts/release_transition_probe.py \
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
    [ -x "$payload/surgepilot-dispatcher" ] || \
        fail "Required release file is not executable: surgepilot-dispatcher"
    [ "$(cat "$payload/VERSION")" = "$RELEASE_VERSION" ] || \
        fail "Release version marker does not match $RELEASE_VERSION."
    manifest_version_lines=$( \
        grep -E '"version"[[:space:]]*:' "$payload/release-manifest.json" || : \
    )
    [ "$manifest_version_lines" = '  "version": "'"$RELEASE_VERSION"'"' ] || \
        fail "Release manifest version does not match $RELEASE_VERSION."
    minimum_lines=$(grep -E '"minimumUpgradeVersion"[[:space:]]*:' \
        "$payload/release-manifest.json" || :)
    [ "$(printf '%s\n' "$minimum_lines" | wc -l | tr -d ' ')" -eq 1 ] || \
        fail "Release manifest minimumUpgradeVersion must appear exactly once."
    minimum_version=$(printf '%s\n' "$minimum_lines" | \
        sed -n 's/^[[:space:]]*"minimumUpgradeVersion":[[:space:]]*"\([^"]*\)"[,]\{0,1\}[[:space:]]*$/\1/p')
    if [ -z "$minimum_version" ] || ! is_canonical_version "$minimum_version"; then
        fail "Release manifest minimumUpgradeVersion is invalid."
    fi
    parse_version "$RELEASE_VERSION"
    manifest_target_major=$VERSION_MAJOR
    manifest_target_minor=$VERSION_MINOR
    manifest_target_patch=$VERSION_PATCH
    parse_version "$minimum_version"
    manifest_minimum_major=$VERSION_MAJOR
    manifest_minimum_minor=$VERSION_MINOR
    manifest_minimum_patch=$VERSION_PATCH
    [ "$manifest_minimum_major" -eq "$manifest_target_major" ] || \
        fail "Release manifest minimumUpgradeVersion crosses the target major."
    if [ "$manifest_minimum_minor" -gt "$manifest_target_minor" ] || \
        { [ "$manifest_minimum_minor" -eq "$manifest_target_minor" ] && \
            [ "$manifest_minimum_patch" -gt "$manifest_target_patch" ]; }; then
        fail "Release manifest minimumUpgradeVersion is newer than the target."
    fi
    MINIMUM_UPGRADE_VERSION=$minimum_version
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
surgepilot/scripts/release_transition_probe.py
surgepilot/surgepilot
surgepilot/surgepilot-dispatcher
EOF
)
    [ "$archive_members" = "$expected_members" ] || \
        fail "Release archive contains unexpected or missing members."
}

validate_legacy_payload() {
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
            fail "Required legacy release file is missing or non-regular: $required"
    done
    [ -x "$payload/surgepilot" ] || \
        fail "Required legacy release file is not executable: surgepilot"
    [ "$(cat "$payload/VERSION")" = "$SOURCE_VERSION" ] || \
        fail "Legacy release version marker does not match $SOURCE_VERSION."
    manifest_version_lines=$( \
        grep -E '"version"[[:space:]]*:' "$payload/release-manifest.json" || : \
    )
    [ "$manifest_version_lines" = '  "version": "'"$SOURCE_VERSION"'"' ] || \
        fail "Legacy release manifest version does not match $SOURCE_VERSION."
}

validate_legacy_archive() {
    archive=$1
    if tar -tvzf "$archive" | grep -E '^[^-d]' >/dev/null 2>&1; then
        fail "Legacy release archive contains an unsupported member type."
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
        fail "Legacy release archive contains unexpected or missing members."
}

shell_quote() {
    escaped=$(printf '%s' "$1" | sed "s/'/'\\\\''/g")
    printf "'%s'" "$escaped"
}

is_canonical_version() {
    printf '%s\n' "$1" | grep -Eq '^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'
}

file_identity() {
    case "$OPERATING_SYSTEM" in
        Linux) stat -c '%u %a' "$1" ;;
        Darwin) stat -f '%u %Lp' "$1" ;;
    esac
}

require_owned_mode() {
    identity=$(file_identity "$1") || fail "$3 cannot be inspected safely."
    [ "$identity" = "$(id -u) $2" ] || fail "$3 has unsafe ownership or permissions."
}

require_owned_directory() {
    identity=$(file_identity "$1") || fail "$2 cannot be inspected safely."
    owner_uid=${identity%% *}
    [ "$owner_uid" = "$(id -u)" ] || fail "$2 has unsafe ownership."
}

require_safe_deployment_layout() {
    require_owned_directory "$INSTALL_ROOT" "Installation root"
    if [ -e "$INSTALL_ROOT/.surgepilot" ] || [ -L "$INSTALL_ROOT/.surgepilot" ]; then
        [ -d "$INSTALL_ROOT/.surgepilot" ] && [ ! -L "$INSTALL_ROOT/.surgepilot" ] || \
            fail "Deployment private state is unsafe."
        require_owned_directory "$INSTALL_ROOT/.surgepilot" "Deployment private state"
    fi
}

parse_version() {
    version_numbers=${1#v}
    VERSION_MAJOR=${version_numbers%%.*}
    version_remainder=${version_numbers#*.}
    VERSION_MINOR=${version_remainder%%.*}
    VERSION_PATCH=${version_remainder#*.}
}

require_supported_upgrade() {
    source_version=$1
    is_canonical_version "$source_version" || fail "Installed source version is malformed."
    parse_version "$source_version"
    source_major=$VERSION_MAJOR source_minor=$VERSION_MINOR source_patch=$VERSION_PATCH
    parse_version "$RELEASE_VERSION"
    target_major=$VERSION_MAJOR target_minor=$VERSION_MINOR target_patch=$VERSION_PATCH
    parse_version "$MINIMUM_UPGRADE_VERSION"
    minimum_major=$VERSION_MAJOR minimum_minor=$VERSION_MINOR minimum_patch=$VERSION_PATCH
    [ "$source_major" -eq "$target_major" ] || fail "Cross-major release transition is not supported."
    if [ "$source_minor" -gt "$target_minor" ] || \
        { [ "$source_minor" -eq "$target_minor" ] && [ "$source_patch" -ge "$target_patch" ]; }; then
        fail "Target release must be newer than the stable source."
    fi
    if [ "$source_major" -lt "$minimum_major" ] || \
        { [ "$source_major" -eq "$minimum_major" ] && [ "$source_minor" -lt "$minimum_minor" ]; } || \
        { [ "$source_major" -eq "$minimum_major" ] && [ "$source_minor" -eq "$minimum_minor" ] && \
            [ "$source_patch" -lt "$minimum_patch" ]; }; then
        fail "Installed source is below the supported upgrade range."
    fi
}

release_lock() {
    if [ "$LOCK_OWNED" != "true" ] || [ ! -f "$LOCK_DIR/owner" ] || \
        [ -L "$LOCK_DIR/owner" ]; then
        return
    fi
    if [ "$(ls -A "$LOCK_DIR" 2>/dev/null)" = owner ] && \
        grep -q "^pid=$$\$" "$LOCK_DIR/owner" && \
        grep -q "^nonce=$LOCK_NONCE\$" "$LOCK_DIR/owner"; then
        rm -f "$LOCK_DIR/owner"
        rmdir "$LOCK_DIR" 2>/dev/null || :
    fi
}

acquire_lock() {
    LOCK_DIR="${INSTALL_ROOT}.lock"
    LOCK_PARENT=${LOCK_DIR%/*}
    OWNER_CANDIDATE=$(mktemp "$LOCK_PARENT/.surgepilot-owner.XXXXXX") || \
        fail "Cannot prepare deployment lock owner state."
    LOCK_NONCE="$$-${OWNER_CANDIDATE##*.}"
    printf 'schema=1\npid=%s\nnonce=%s\n' "$$" "$LOCK_NONCE" > "$OWNER_CANDIDATE" || \
        fail "Cannot write deployment lock owner state."
    if ! mkdir -m 700 "$LOCK_DIR" 2>/dev/null; then
        [ -d "$LOCK_DIR" ] && [ ! -L "$LOCK_DIR" ] && \
            [ -f "$LOCK_DIR/owner" ] && [ ! -L "$LOCK_DIR/owner" ] || \
            fail "Deployment lock state is unsafe at $LOCK_DIR; inspect it manually."
        require_owned_mode "$LOCK_DIR" 700 "Deployment lock"
        require_owned_mode "$LOCK_DIR/owner" 600 "Deployment lock owner"
        [ "$(ls -A "$LOCK_DIR" 2>/dev/null)" = owner ] || \
            fail "Deployment lock state is unsafe at $LOCK_DIR; inspect it manually."
        {
            IFS= read -r owner_schema || fail "Deployment lock owner state is unsafe."
            IFS= read -r owner_pid_line || fail "Deployment lock owner state is unsafe."
            IFS= read -r owner_nonce_line || fail "Deployment lock owner state is unsafe."
            if IFS= read -r _; then fail "Deployment lock owner state is unsafe."; fi
        } < "$LOCK_DIR/owner"
        owner_pid=${owner_pid_line#pid=}
        owner_nonce=${owner_nonce_line#nonce=}
        [ "$owner_schema" = schema=1 ] && [ "$owner_pid_line" = "pid=$owner_pid" ] && \
            [ "$owner_nonce_line" = "nonce=$owner_nonce" ] && [ -n "$owner_nonce" ] || \
            fail "Deployment lock owner state is unsafe; inspect $LOCK_DIR manually."
        case "$owner_pid" in ''|*[!0-9]*)
            fail "Deployment lock owner state is unsafe; inspect $LOCK_DIR manually." ;;
        esac
        if kill -0 "$owner_pid" 2>/dev/null || ps -p "$owner_pid" >/dev/null 2>&1; then
            fail "Another SurgePilot command is running with PID $owner_pid."
        fi
        fail "A stale deployment lock exists at $LOCK_DIR; verify no SurgePilot command is running before removing that exact directory."
    fi
    if ! mv "$OWNER_CANDIDATE" "$LOCK_DIR/owner"; then
        OWNER_CANDIDATE=
        fail "Cannot publish deployment lock owner state; inspect $LOCK_DIR manually."
    fi
    OWNER_CANDIDATE=
    LOCK_OWNED=true
    require_owned_mode "$LOCK_DIR" 700 "Deployment lock"
    require_owned_mode "$LOCK_DIR/owner" 600 "Deployment lock owner"
}

read_state() {
    state_file=$INSTALL_ROOT/.release-state
    [ -f "$state_file" ] && [ ! -L "$state_file" ] || fail "Release state is missing or unsafe."
    require_owned_mode "$state_file" 600 "Release state"
    {
        IFS= read -r schema_line || fail "Release state is incomplete."
        IFS= read -r phase_line || fail "Release state is incomplete."
        IFS= read -r target_line || fail "Release state is incomplete."
        IFS= read -r base_line || fail "Release state is incomplete."
        if IFS= read -r _; then fail "Release state contains unexpected fields."; fi
    } < "$state_file"
    [ "$schema_line" = schema=1 ] || fail "Release state schema is unsupported."
    STATE_PHASE=${phase_line#phase=}
    STATE_TARGET=${target_line#target=}
    STATE_BASE=${base_line#base=}
    [ "$phase_line" = "phase=$STATE_PHASE" ] && [ "$target_line" = "target=$STATE_TARGET" ] && \
        [ "$base_line" = "base=$STATE_BASE" ] || fail "Release state is malformed."
    is_canonical_version "$STATE_TARGET" || fail "Release state target is malformed."
    case "$STATE_BASE" in none) ;; *) is_canonical_version "$STATE_BASE" || \
        fail "Release state base is malformed." ;; esac
    case "$STATE_PHASE" in
        installed) [ "$STATE_BASE" = none ] || fail "Release state fields are inconsistent." ;;
        stable) [ "$STATE_BASE" = "$STATE_TARGET" ] || fail "Release state fields are inconsistent." ;;
        unclassified|prepared) [ "$STATE_BASE" != none ] || fail "Release state fields are inconsistent." ;;
        migration_started) ;;
        *) fail "Release state phase is unsupported." ;;
    esac
}

write_state() {
    next_phase=$1 next_target=$2 next_base=$3
    candidate=$(mktemp "$INSTALL_ROOT/.release-state.XXXXXX") || fail "Cannot prepare release state."
    printf 'schema=1\nphase=%s\ntarget=%s\nbase=%s\n' \
        "$next_phase" "$next_target" "$next_base" > "$candidate" || \
        fail "Cannot write release state."
    chmod 600 "$candidate" || fail "Cannot protect release state."
    sync || fail "Cannot confirm release state durability."
    mv "$candidate" "$INSTALL_ROOT/.release-state" || fail "Cannot publish release state."
    sync || fail "Cannot confirm release state durability."
}

verify_release_directory() {
    existing=$1 payload=$2
    [ -d "$existing" ] && [ ! -L "$existing" ] || fail "Installed release directory is unsafe."
    [ -L "$existing/.surgepilot" ] && \
        [ "$(readlink "$existing/.surgepilot")" = ../../.surgepilot ] || \
        fail "Installed release private-state bridge is invalid."
    verify_payload_files "$existing" "$payload"
    actual_members=$(cd "$existing" && find . -mindepth 1 -print | LC_ALL=C sort)
    expected_members=$(cat <<'EOF'
./.env.example
./.surgepilot
./README.md
./VERSION
./compose
./compose/docker-compose.yml
./compose/grafana
./compose/grafana/dashboards
./compose/grafana/dashboards/surgepilot-jmeter-13644.json
./compose/grafana/entrypoint.sh
./compose/grafana/provisioning
./compose/grafana/provisioning/dashboards
./compose/grafana/provisioning/dashboards/surgepilot.yml
./compose/grafana/provisioning/datasources
./compose/grafana/provisioning/datasources/influxdb.yml
./compose/minio
./compose/minio/init-bucket.sh
./compose/nginx
./compose/nginx/default.conf
./release-manifest.json
./scripts
./scripts/__init__.py
./scripts/bootstrap_deployment_env.py
./scripts/fetch_runtime_release.py
./scripts/release_preflight.py
./scripts/release_transition_probe.py
./surgepilot
./surgepilot-dispatcher
EOF
)
    [ "$actual_members" = "$expected_members" ] || \
        fail "Installed release directory contains unexpected or missing members."
}

verify_payload_files() {
    existing=$1 payload=$2
    for relative in surgepilot surgepilot-dispatcher compose/docker-compose.yml .env.example \
        VERSION README.md release-manifest.json scripts/__init__.py \
        scripts/bootstrap_deployment_env.py scripts/fetch_runtime_release.py \
        scripts/release_preflight.py scripts/release_transition_probe.py \
        compose/grafana/dashboards/surgepilot-jmeter-13644.json \
        compose/grafana/entrypoint.sh \
        compose/grafana/provisioning/dashboards/surgepilot.yml \
        compose/grafana/provisioning/datasources/influxdb.yml \
        compose/minio/init-bucket.sh compose/nginx/default.conf
    do
        [ -f "$existing/$relative" ] && [ ! -L "$existing/$relative" ] || \
            fail "Installed release member is missing or unsafe: $relative"
        cmp -s "$existing/$relative" "$payload/$relative" || \
            fail "Installed release member differs from the verified payload: $relative"
    done
    [ -x "$existing/surgepilot" ] && [ -x "$existing/surgepilot-dispatcher" ] || \
        fail "Installed release executables are unsafe."
}

verify_legacy_payload_files() {
    existing=$1 payload=$2
    for relative in surgepilot compose/docker-compose.yml .env.example VERSION README.md \
        release-manifest.json scripts/__init__.py scripts/bootstrap_deployment_env.py \
        scripts/fetch_runtime_release.py scripts/release_preflight.py \
        compose/grafana/dashboards/surgepilot-jmeter-13644.json \
        compose/grafana/entrypoint.sh \
        compose/grafana/provisioning/dashboards/surgepilot.yml \
        compose/grafana/provisioning/datasources/influxdb.yml \
        compose/minio/init-bucket.sh compose/nginx/default.conf
    do
        [ -f "$existing/$relative" ] && [ ! -L "$existing/$relative" ] || \
            fail "Installed legacy release member is missing or unsafe: $relative"
        cmp -s "$existing/$relative" "$payload/$relative" || \
            fail "Installed legacy release member differs from the verified payload: $relative"
    done
    [ -x "$existing/surgepilot" ] || fail "Installed legacy release wrapper is unsafe."
}

verify_legacy_release_directory() {
    existing=$1 payload=$2
    [ -d "$existing" ] && [ ! -L "$existing" ] || \
        fail "Installed legacy release directory is unsafe."
    [ -L "$existing/.surgepilot" ] && \
        [ "$(readlink "$existing/.surgepilot")" = ../../.surgepilot ] || \
        fail "Installed legacy release private-state bridge is invalid."
    verify_legacy_payload_files "$existing" "$payload"
    actual_members=$(cd "$existing" && find . -mindepth 1 -print | LC_ALL=C sort)
    expected_members=$(cat <<'EOF'
./.env.example
./.surgepilot
./README.md
./VERSION
./compose
./compose/docker-compose.yml
./compose/grafana
./compose/grafana/dashboards
./compose/grafana/dashboards/surgepilot-jmeter-13644.json
./compose/grafana/entrypoint.sh
./compose/grafana/provisioning
./compose/grafana/provisioning/dashboards
./compose/grafana/provisioning/dashboards/surgepilot.yml
./compose/grafana/provisioning/datasources
./compose/grafana/provisioning/datasources/influxdb.yml
./compose/minio
./compose/minio/init-bucket.sh
./compose/nginx
./compose/nginx/default.conf
./release-manifest.json
./scripts
./scripts/__init__.py
./scripts/bootstrap_deployment_env.py
./scripts/fetch_runtime_release.py
./scripts/release_preflight.py
./surgepilot
EOF
)
    [ "$actual_members" = "$expected_members" ] || \
        fail "Installed legacy release directory contains unexpected or missing members."
}

publish_release_directory() {
    payload=$1
    release_version=${2:-$RELEASE_VERSION}
    release_format=${3:-current}
    releases=$INSTALL_ROOT/.releases
    [ -d "$releases" ] && [ ! -L "$releases" ] || fail "Installed release store is unsafe."
    final=$releases/$release_version
    if [ -e "$final" ] || [ -L "$final" ]; then
        if [ "$release_format" = legacy ]; then
            verify_legacy_release_directory "$final" "$payload"
        else
            verify_release_directory "$final" "$payload"
        fi
        return
    fi
    STAGED_RELEASE=$(mktemp -d "$releases/.${release_version}.XXXXXX") || \
        fail "Cannot stage target release."
    cp -R "$payload/." "$STAGED_RELEASE/" || fail "Cannot copy target release."
    ln -s ../../.surgepilot "$STAGED_RELEASE/.surgepilot" || \
        fail "Cannot link deployment private state."
    sync || fail "Cannot confirm target release durability."
    mv "$STAGED_RELEASE" "$final" || fail "Cannot publish target release."
    STAGED_RELEASE=
    sync || fail "Cannot confirm target release durability."
}

download_legacy_payload() {
    source_version=$1
    source_archive_name="surgepilot-${source_version}.tar.gz"
    source_sidecar_name="${source_archive_name}.sha256"
    if [ "${SURGEPILOT_INSTALLER_RELEASE_BASE_URL+x}" = x ]; then
        source_base_url=$RELEASE_BASE_URL
    else
        source_base_url="https://github.com/${REPOSITORY}/releases/download/${source_version}"
    fi
    source_archive=$WORK_DIR/$source_archive_name
    source_sidecar=$WORK_DIR/$source_sidecar_name
    download "$source_base_url/$source_archive_name" "$source_archive"
    download "$source_base_url/$source_sidecar_name" "$source_sidecar"
    IFS=' ' read -r source_expected source_recorded source_extra < "$source_sidecar" || \
        fail "Legacy checksum sidecar is invalid."
    case "$source_expected" in *[!0-9a-f]*|'') fail "Legacy checksum sidecar is invalid." ;; esac
    [ "${#source_expected}" -eq 64 ] && [ "$source_recorded" = "$source_archive_name" ] && \
        [ -z "${source_extra:-}" ] || fail "Legacy checksum sidecar is invalid."
    [ "$(calculate_sha256 "$source_archive")" = "$source_expected" ] || \
        fail "Legacy bundle checksum verification failed."
    validate_legacy_archive "$source_archive"
    source_extract=$WORK_DIR/source-extracted
    mkdir "$source_extract" || fail "Cannot prepare legacy extracted release state."
    tar -xzf "$source_archive" -C "$source_extract" || fail "Legacy bundle extraction failed."
    SOURCE_PAYLOAD=$source_extract/surgepilot
    SOURCE_VERSION=$source_version
    validate_legacy_payload "$SOURCE_PAYLOAD"
}

prepare_legacy_upgrade() {
    target_payload=$1
    [ "$RELEASE_VERSION" = v1.2.0 ] || \
        fail "Legacy installation transition is supported only by v1.2.0."
    [ -f "$INSTALL_ROOT/VERSION" ] && [ ! -L "$INSTALL_ROOT/VERSION" ] || \
        fail "Legacy installation VERSION is missing or unsafe."
    source_version=$(cat "$INSTALL_ROOT/VERSION")
    case "$source_version" in v1.0.0|v1.1.0) ;; *)
        fail "Legacy source $source_version is not supported." ;;
    esac
    require_supported_upgrade "$source_version"
    download_legacy_payload "$source_version"

    acquire_lock
    require_safe_deployment_layout
    [ "$(cat "$INSTALL_ROOT/VERSION")" = "$source_version" ] || \
        fail "Legacy installation changed while preparing the transition."
    mkdir -p "$INSTALL_ROOT/.releases" || fail "Cannot prepare installed release store."
    [ -d "$INSTALL_ROOT/.releases" ] && [ ! -L "$INSTALL_ROOT/.releases" ] || \
        fail "Installed release store is unsafe."

    if cmp -s "$INSTALL_ROOT/surgepilot" "$target_payload/surgepilot-dispatcher"; then
        verify_legacy_release_directory \
            "$INSTALL_ROOT/.releases/$source_version" "$SOURCE_PAYLOAD"
        verify_release_directory "$INSTALL_ROOT/.releases/$RELEASE_VERSION" "$target_payload"
        write_state unclassified "$RELEASE_VERSION" "$source_version"
        printf 'Recovered SurgePilot %s transition preparation from %s.\n' \
            "$RELEASE_VERSION" "$source_version"
        return
    fi

    verify_legacy_payload_files "$INSTALL_ROOT" "$SOURCE_PAYLOAD"
    publish_release_directory "$SOURCE_PAYLOAD" "$source_version" legacy
    publish_release_directory "$target_payload" "$RELEASE_VERSION"
    dispatcher_candidate=$(mktemp "$INSTALL_ROOT/.surgepilot-dispatcher.XXXXXX") || \
        fail "Cannot stage the release dispatcher."
    cp "$target_payload/surgepilot-dispatcher" "$dispatcher_candidate" || \
        fail "Cannot copy the release dispatcher."
    chmod 700 "$dispatcher_candidate" || fail "Cannot protect the release dispatcher."
    sync || fail "Cannot confirm dispatcher durability."
    mv "$dispatcher_candidate" "$INSTALL_ROOT/surgepilot" || \
        fail "Cannot publish the release dispatcher."
    sync || fail "Cannot confirm dispatcher durability."
    write_state unclassified "$RELEASE_VERSION" "$source_version"
    printf 'SurgePilot %s is prepared from legacy %s.\n' "$RELEASE_VERSION" "$source_version"
    printf 'Back up persistent data, then run surgepilot up to apply the transition.\n'
}

prepare_schema1_upgrade() {
    payload=$1
    acquire_lock
    require_safe_deployment_layout
    read_state
    [ -f "$INSTALL_ROOT/surgepilot" ] && [ ! -L "$INSTALL_ROOT/surgepilot" ] && \
        [ -x "$INSTALL_ROOT/surgepilot" ] || fail "Installed dispatcher is unsafe."
    require_owned_mode "$INSTALL_ROOT/surgepilot" 700 "Installed dispatcher"
    cmp -s "$INSTALL_ROOT/surgepilot" "$payload/surgepilot-dispatcher" || \
        fail "Installed dispatcher differs from the verified target dispatcher."
    if [ "$STATE_TARGET" = "$RELEASE_VERSION" ]; then
        verify_release_directory "$INSTALL_ROOT/.releases/$RELEASE_VERSION" "$payload"
        printf 'SurgePilot %s is already prepared; release state is unchanged.\n' "$RELEASE_VERSION"
        return
    fi
    [ "$STATE_PHASE" = stable ] || \
        fail "A different target can be prepared only from stable release state."
    require_supported_upgrade "$STATE_TARGET"
    publish_release_directory "$payload"
    write_state prepared "$RELEASE_VERSION" "$STATE_TARGET"
    printf 'SurgePilot %s is prepared from %s.\n' "$RELEASE_VERSION" "$STATE_TARGET"
    printf 'Run surgepilot up to apply the transition.\n'
}

prepare_fresh_installation() {
    payload=$1
    candidate=$2
    release_root="$candidate/.releases/$RELEASE_VERSION"
    mkdir -p "$release_root" || fail "Cannot prepare the release directory."
    cp -R "$payload/." "$release_root/" || fail "Cannot stage the release payload."
    ln -s ../../.surgepilot "$release_root/.surgepilot" || \
        fail "Cannot link deployment private state."
    cp "$release_root/surgepilot-dispatcher" "$candidate/surgepilot" || \
        fail "Cannot stage the release dispatcher."
    chmod 700 "$candidate/surgepilot" || fail "Cannot protect the release dispatcher."
    printf 'schema=1\nphase=installed\ntarget=%s\nbase=none\n' "$RELEASE_VERSION" > \
        "$candidate/.release-state" || fail "Cannot stage release state."
    chmod 600 "$candidate/.release-state" || fail "Cannot protect release state."
}

publish_installation() {
    candidate=$1
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
    mv "$candidate" "$INSTALL_ROOT" || fail "Cannot publish the installation root."
    PUBLISHED_ROOT=$INSTALL_ROOT
    sync || fail "Cannot confirm installation root durability."
    if ! mv "$LAUNCHER_TEMP" "$LAUNCHER"; then
        rm -f "$LAUNCHER_TEMP"
        LAUNCHER_TEMP=
        rm -rf "$PUBLISHED_ROOT"
        PUBLISHED_ROOT=
        fail "Cannot publish the launcher."
    fi
    LAUNCHER_TEMP=
    sync || fail "Cannot confirm launcher durability."
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

for command_name in cat curl tar mktemp mkdir rm rmdir mv chmod grep sed sort uname cp ln \
    cmp sync readlink ps ls wc tr stat id find
do
    require_command "$command_name"
done

OPERATING_SYSTEM=$(uname -s)
case "$OPERATING_SYSTEM" in
    Linux) require_command sha256sum ;;
    Darwin) require_command shasum ;;
    *) fail "Unsupported operating system: $OPERATING_SYSTEM" ;;
esac

if [ -e "$INSTALL_ROOT" ] || [ -L "$INSTALL_ROOT" ]; then
    [ -d "$INSTALL_ROOT" ] && [ ! -L "$INSTALL_ROOT" ] || \
        fail "Installation root already exists and is unsafe: $INSTALL_ROOT"
    EXISTING_INSTALLATION=true
    [ -f "$LAUNCHER" ] && [ ! -L "$LAUNCHER" ] && [ -x "$LAUNCHER" ] || \
        fail "Existing installation launcher is missing or unsafe: $LAUNCHER"
else
    EXISTING_INSTALLATION=false
    [ ! -e "$LAUNCHER" ] && [ ! -L "$LAUNCHER" ] || \
        fail "Launcher already exists: $LAUNCHER"
fi

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

if [ "$EXISTING_INSTALLATION" = true ]; then
    if [ -e "$INSTALL_ROOT/.release-state" ] || [ -L "$INSTALL_ROOT/.release-state" ]; then
        prepare_schema1_upgrade "$PAYLOAD"
        exit 0
    fi
    prepare_legacy_upgrade "$PAYLOAD"
    exit 0
fi

INSTALL_CANDIDATE="$WORK_DIR/installation"
mkdir "$INSTALL_CANDIDATE" || fail "Cannot prepare the installation root."
prepare_fresh_installation "$PAYLOAD" "$INSTALL_CANDIDATE"
publish_installation "$INSTALL_CANDIDATE"

printf 'SurgePilot %s installed in %s\n' "$RELEASE_VERSION" "$INSTALL_ROOT"
printf 'Launcher: %s\n' "$LAUNCHER"
printf 'Run surgepilot up from an interactive terminal.\n'
case ":${PATH:-}:" in
    *":$LAUNCHER_PARENT:"*) ;;
    *)
        printf 'If surgepilot is not found, run %s up or add it for this shell:\n' "$LAUNCHER"
        # shellcheck disable=SC2016
        printf '  export PATH="%s:$PATH"\n' "$LAUNCHER_PARENT"
        ;;
esac
