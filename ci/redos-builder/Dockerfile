ARG REDOS_BASE=registry.red-soft.ru/ubi8/ubi@sha256:8ff657eea9666b984dfd37b1b3296e98d1cbc95038a849204d1b67d69978fe5c
FROM ${REDOS_BASE} AS toolchain

RUN dnf -y --disablerepo='*' --enablerepo=base,updates \
      --setopt=gpgcheck=1 --setopt=install_weak_deps=False --setopt=tsflags=nodocs install \
      golang-1.26.6-1.red80.x86_64 \
      nodejs-1:24.19.0-1.red80.x86_64 \
      nodejs-npm-1:11.17.0-1.24.19.0.1.red80.x86_64 \
      python3 gcc gcc-c++ pkgconf-pkg-config git file \
      gtk3-devel-3.24.49-1.red80.x86_64 \
      webkit2gtk4.1-devel-1:2.50.4-2.red80.x86_64 \
    && dnf clean all \
    && go version && node --version && npm --version \
    && pkg-config --modversion gtk+-3.0 webkit2gtk-4.1

ENV GOFLAGS=-mod=vendor GOPROXY=off GOSUMDB=off GOWORK=off GOTOOLCHAIN=local \
    npm_config_offline=true npm_config_audit=false npm_config_fund=false \
    npm_config_update_notifier=false PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

FROM toolchain AS wails-builder
COPY wails/ /src/wails/
RUN cd /src/wails \
    && test "$(cat cmd/wails/internal/version.txt)" = v2.15.0 \
    && CGO_ENABLED=0 go build -mod=vendor -trimpath -o /usr/local/bin/wails ./cmd/wails \
    && /usr/local/bin/wails version

FROM toolchain AS npm-cache
COPY npm-tarballs/ /src/npm-tarballs/
RUN npm cache add --offline --cache /opt/npm-cache --no-audit --no-fund /src/npm-tarballs/*.tgz \
    && chmod -R a+rX /opt/npm-cache

FROM toolchain AS builder
COPY --from=wails-builder /usr/local/bin/wails /usr/local/bin/wails
COPY --from=wails-builder /src/wails/SOURCE.json /usr/share/wails/SOURCE.json
COPY --from=wails-builder /src/wails/LICENSE /usr/share/licenses/wails/LICENSE
COPY --from=npm-cache /opt/npm-cache /opt/npm-cache
COPY frontend/ /opt/builder-inputs/
COPY build-target.sh /usr/local/bin/build-installer
RUN chmod 755 /usr/local/bin/build-installer && wails version \
    && rpm -qa --qf '%{NAME} %{VERSION}-%{RELEASE} %{ARCH}\n' | sort > /usr/share/wails/builder-rpms.txt
WORKDIR /workspace
CMD ["bash"]
