FROM ubuntu:24.04

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy
ARG APT_MIRROR
ARG APT_SECURITY_MIRROR
ARG SURGEPILOT_VERSION=dev
ARG SURGEPILOT_REVISION=unknown
ARG SURGEPILOT_SOURCE=https://github.com/latentrun/SurgePilot

LABEL org.opencontainers.image.source=${SURGEPILOT_SOURCE} \
      org.opencontainers.image.revision=${SURGEPILOT_REVISION} \
      org.opencontainers.image.version=${SURGEPILOT_VERSION}

ENV DEBIAN_FRONTEND=noninteractive

RUN set -eu; \
    validate_mirror() { \
        value="$1"; name="$2"; \
        if [ -z "$value" ]; then return 0; fi; \
        case "$value" in http://*|https://*) ;; *) echo "$name must use http or https" >&2; exit 1 ;; esac; \
        if printf '%s' "$value" | grep -Eq '[[:space:]]'; then echo "$name must not contain whitespace" >&2; exit 1; fi; \
    }; \
    escape_sed() { printf '%s' "$1" | sed 's/[\\&|]/\\&/g'; }; \
    validate_mirror "${APT_MIRROR:-}" APT_MIRROR; \
    validate_mirror "${APT_SECURITY_MIRROR:-}" APT_SECURITY_MIRROR; \
    mirror="${APT_MIRROR:-}"; security_mirror="${APT_SECURITY_MIRROR:-${APT_MIRROR:-}}"; \
    if [ -n "$mirror" ]; then \
        mirror="$(escape_sed "${mirror%/}")"; \
        find /etc/apt/sources.list.d -name '*.sources' -type f -exec sed -i -E \
            "s|https?://archive\\.ubuntu\\.com/ubuntu/?|$mirror|g; s|https?://ports\\.ubuntu\\.com/ubuntu-ports/?|$mirror|g" {} +; \
    fi; \
    if [ -n "$security_mirror" ]; then \
        security_mirror="$(escape_sed "${security_mirror%/}")"; \
        find /etc/apt/sources.list.d -name '*.sources' -type f -exec sed -i -E \
            "s|https?://security\\.ubuntu\\.com/ubuntu/?|$security_mirror|g" {} +; \
    fi; \
    apt-get -o Acquire::Retries=3 update; \
    apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
        ca-certificates \
        openjdk-17-jre-headless \
        openssh-server \
        procps \
        python3 \
        python3-click \
        tar; \
    rm -rf /var/lib/apt/lists/* /etc/ssh/ssh_host_*; \
    useradd -m -s /bin/bash surgepilot; \
    passwd -l surgepilot; \
    mkdir -p /run/sshd /opt/surgepilot/runner; \
    chown -R surgepilot:surgepilot /opt/surgepilot /home/surgepilot; \
    sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config; \
    sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config; \
    printf '\nAllowUsers surgepilot\n' >> /etc/ssh/sshd_config

COPY infra/docker/demo-load-node/entrypoint.sh /usr/local/bin/surgepilot-demo-node-entrypoint
RUN chmod 0755 /usr/local/bin/surgepilot-demo-node-entrypoint

EXPOSE 22
HEALTHCHECK --interval=5s --timeout=3s --retries=20 CMD pgrep -x sshd >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/surgepilot-demo-node-entrypoint"]
CMD ["/usr/sbin/sshd", "-D", "-e"]
