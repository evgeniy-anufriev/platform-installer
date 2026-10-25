#!/bin/sh
set -eu
exec /bin/sh ./application-packages/keycloak/1.0.0/assets/scripts/integration.sh "$@"
