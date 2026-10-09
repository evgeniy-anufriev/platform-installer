#!/usr/bin/env bash
set -euo pipefail

# QA-only build from source and binaries already installed on the trusted RED OS host.
cd "$(dirname "$0")"
test -f main.go
test -x /usr/bin/go
GO111MODULE=off CGO_ENABLED=0 /usr/bin/go build -trimpath -ldflags='-s -w' -o connection-probe main.go
test -x /usr/bin/vault
test -x /usr/bin/psql
test -x /usr/bin/openssl
sudo -n -u platform-docker test -S /run/user/"$(id -u platform-docker)"/docker.sock

mkdir -p rootfs
find rootfs -type d -exec chmod u+w {} +
find rootfs -type f -exec chmod u+w {} +
for binary in /usr/bin/vault /usr/bin/psql /usr/bin/openssl; do
  mkdir -p "rootfs$(dirname "$binary")"
  chmod u+w "rootfs$(dirname "$binary")"
  cp -L --parents "$binary" rootfs/
  ldd "$binary" | awk '{for (i=1;i<=NF;i++) if ($i ~ /^\//) print $i}' | while read -r lib; do
    test -f "$lib"
    mkdir -p "rootfs$(dirname "$lib")"
    chmod u+w "rootfs$(dirname "$lib")"
    cp -L --parents "$lib" rootfs/
  done
done

for nss in /lib64/libnss_dns.so.2 /lib64/libnss_files.so.2; do
  if test -f "$nss"; then cp -L --parents "$nss" rootfs/; fi
done
mkdir -p rootfs/etc/ssl/certs rootfs/tmp rootfs/run/probe
chmod u+w rootfs/etc/ssl/certs rootfs/etc
chmod 1777 rootfs/tmp
cp /etc/nsswitch.conf rootfs/etc/nsswitch.conf
test -f /etc/ssl/certs/ca-bundle.crt && cp /etc/ssl/certs/ca-bundle.crt rootfs/etc/ssl/certs/ca-certificates.crt

docker_uid="$(id -u platform-docker)"
sudo -n -u platform-docker env XDG_RUNTIME_DIR="/run/user/$docker_uid" \
  DOCKER_HOST="unix:///run/user/$docker_uid/docker.sock" \
  docker build --pull=false -t platform-application-connection-probe:qa -f Dockerfile .
sudo -n -u platform-docker env XDG_RUNTIME_DIR="/run/user/$docker_uid" \
  DOCKER_HOST="unix:///run/user/$docker_uid/docker.sock" \
  docker image inspect platform-application-connection-probe:qa --format '{{.Id}}'
