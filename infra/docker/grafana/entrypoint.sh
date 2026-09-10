#!/bin/sh
set -eu

source_token=/run/secrets/surgepilot_influxdb_token
projected_directory=/run/surgepilot
projected_token=/run/surgepilot/influxdb-token

if [ ! -r "$source_token" ]; then
    echo "Grafana bootstrap token is not readable." >&2
    exit 1
fi

grafana_uid=$(id -u grafana)
grafana_gid=$(id -g grafana)
mkdir -p "$projected_directory"
chown 0:0 "$projected_directory"
chmod 710 "$projected_directory"
cat "$source_token" > "$projected_token"
chown "$grafana_uid:$grafana_gid" "$projected_token"
chmod 400 "$projected_token"

if [ ! -s "$projected_token" ]; then
    echo "Grafana bootstrap token is empty." >&2
    exit 1
fi

export GF_SECURITY_ADMIN_PASSWORD__FILE="$projected_token"

exec su -p -s /bin/sh grafana -c 'exec /run.sh'
