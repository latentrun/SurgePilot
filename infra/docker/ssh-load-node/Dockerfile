FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy
ARG APT_MIRROR
ARG APT_SECURITY_MIRROR

RUN set -eu; \
    validate_apt_mirror() { \
        value="$1"; \
        name="$2"; \
        if [ -z "$value" ]; then return 0; fi; \
        case "$value" in \
            http://*|https://*) ;; \
            *) echo "$name must start with http:// or https://" >&2; exit 1 ;; \
        esac; \
        if printf '%s' "$value" | grep -Eq '[[:space:]]'; then \
            echo "$name must not contain whitespace" >&2; \
            exit 1; \
        fi; \
    }; \
    escape_sed_replacement() { \
        printf '%s' "$1" | sed 's/[\\&|]/\\&/g'; \
    }; \
    validate_apt_mirror "${APT_MIRROR:-}" "APT_MIRROR"; \
    validate_apt_mirror "${APT_SECURITY_MIRROR:-}" "APT_SECURITY_MIRROR"; \
    apt_mirror="${APT_MIRROR:-}"; \
    apt_security_mirror="${APT_SECURITY_MIRROR:-}"; \
    if [ -n "$apt_mirror" ]; then apt_mirror="${apt_mirror%/}"; fi; \
    if [ -n "$apt_security_mirror" ]; then apt_security_mirror="${apt_security_mirror%/}"; fi; \
    if [ -n "$apt_mirror" ] && [ -z "$apt_security_mirror" ]; then \
        apt_security_mirror="$apt_mirror"; \
    fi; \
    apt_mirror_sed="$(escape_sed_replacement "$apt_mirror")"; \
    apt_security_mirror_sed="$(escape_sed_replacement "$apt_security_mirror")"; \
    if [ -n "$apt_mirror" ] || [ -n "$apt_security_mirror" ]; then \
        if [ -n "$apt_mirror" ]; then \
            if [ -d /etc/apt/sources.list.d ]; then \
                find /etc/apt/sources.list.d -name '*.sources' -type f -exec sed -i -E \
                    "s|https?://archive\\.ubuntu\\.com/ubuntu/?|${apt_mirror_sed}|g; s|https?://ports\\.ubuntu\\.com/ubuntu-ports/?|${apt_mirror_sed}|g" {} +; \
            fi; \
            if [ -f /etc/apt/sources.list ]; then \
                sed -i -E \
                    "s|https?://archive\\.ubuntu\\.com/ubuntu/?|${apt_mirror_sed}|g; s|https?://ports\\.ubuntu\\.com/ubuntu-ports/?|${apt_mirror_sed}|g" \
                    /etc/apt/sources.list; \
            fi; \
        fi; \
        if [ -n "$apt_security_mirror" ]; then \
            if [ -d /etc/apt/sources.list.d ]; then \
                find /etc/apt/sources.list.d -name '*.sources' -type f -exec sed -i -E \
                    "s|https?://security\\.ubuntu\\.com/ubuntu/?|${apt_security_mirror_sed}|g" {} +; \
            fi; \
            if [ -f /etc/apt/sources.list ]; then \
                sed -i -E "s|https?://security\\.ubuntu\\.com/ubuntu/?|${apt_security_mirror_sed}|g" \
                    /etc/apt/sources.list; \
            fi; \
        fi; \
    fi; \
    apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
        ca-certificates \
        openjdk-17-jre-headless \
        openssh-server \
        procps \
        python3 \
        python3-click \
        tar \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash surgepilot \
    && echo "surgepilot:surgepilot" | chpasswd \
    && mkdir -p /run/sshd /opt/surgepilot/runner \
    && chown -R surgepilot:surgepilot /opt/surgepilot /home/surgepilot \
    && sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config \
    && printf '\nAllowUsers surgepilot\n' >> /etc/ssh/sshd_config

EXPOSE 22

HEALTHCHECK --interval=5s --timeout=3s --retries=20 CMD pgrep -x sshd >/dev/null || exit 1

CMD ["/usr/sbin/sshd", "-D", "-e"]
