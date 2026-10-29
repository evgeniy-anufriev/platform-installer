#!/bin/sh
# ordinary-project-dir windows/amd64|linux/amd64
set -eu
if [ "$#" -ne 2 ]; then
    echo 'Usage: build-installer PROJECT_DIR windows/amd64|linux/amd64' >&2
    exit 2
fi
project_dir=$(realpath "$1")
target=$2
case "$target" in
    windows/amd64) export CGO_ENABLED=0 ;;
    linux/amd64) export CGO_ENABLED=1 ;;
    *) echo 'Unsupported build target' >&2; exit 2 ;;
esac
export GOFLAGS=-mod=vendor GOPROXY=off GOSUMDB=off GOWORK=off GOTOOLCHAIN=local
export npm_config_offline=true npm_config_audit=false npm_config_fund=false
export npm_config_update_notifier=false PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
python3 - "$project_dir" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
for name in ('package.json', 'package-lock.json'):
    expected = json.loads((pathlib.Path('/opt/builder-inputs') / name).read_text())
    actual = json.loads((root / 'frontend' / name).read_text())
    if expected != actual:
        raise SystemExit('Builder image npm closure does not match ' + name + '; rebuild the image')
PY
HOME=$(mktemp -d /tmp/installer-home-XXXXXX)
export HOME
export GOCACHE="${GOCACHE:-$HOME/go-build}" GOPATH="${GOPATH:-$HOME/go-path}"
cache_dir=$(mktemp -d /tmp/npm-builder-XXXXXX)
trap 'rm -rf -- "$cache_dir" "$HOME"' EXIT
cp -R /opt/npm-cache/. "$cache_dir/"
cd "$project_dir/frontend"
npm ci --offline --cache "$cache_dir" --no-audit --no-fund
npm run build
cd "$project_dir"
case "$target" in
    windows/amd64)
        wails build -platform "$target" -nopackage -clean -m -nosyncgomod -skipbindings -s
        sha256sum build/bin/platform-installer-ui.exe
        file build/bin/platform-installer-ui.exe
        ;;
    linux/amd64)
        wails build -platform "$target" -tags webkit2_41 -nopackage -clean -m -nosyncgomod -skipbindings -s
        sha256sum build/bin/platform-installer-ui
        file build/bin/platform-installer-ui
        ldd build/bin/platform-installer-ui
        mkdir -p build/bin/linux-resources
        cp build/linux/platform-installer-ui.desktop build/bin/linux-resources/
        cp build/linux/icon.png build/bin/linux-resources/platform-installer-ui.png
        ;;
esac
