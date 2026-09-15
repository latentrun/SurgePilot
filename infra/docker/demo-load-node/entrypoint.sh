#!/bin/sh
set -eu

password_file=/run/secrets/surgepilot_demo_password
host_key_dir=/run/surgepilot/host-keys
private_key="$host_key_dir/ssh_host_ed25519_key"
public_key="$host_key_dir/ssh_host_ed25519_key.pub"

for path in "$password_file" "$private_key" "$public_key"; do
    if [ ! -f "$path" ] || [ -L "$path" ] || [ ! -s "$path" ]; then
        printf 'Demo Load Node state file is missing or unsafe: %s\n' "$path" >&2
        exit 1
    fi
done

install -m 0600 "$private_key" /etc/ssh/ssh_host_ed25519_key
install -m 0644 "$public_key" /etc/ssh/ssh_host_ed25519_key.pub
password=$(cat "$password_file")
if [ -z "$password" ]; then
    printf 'Demo Load Node password is empty.\n' >&2
    exit 1
fi
printf 'surgepilot:%s\n' "$password" | chpasswd
unset password

exec "$@"
