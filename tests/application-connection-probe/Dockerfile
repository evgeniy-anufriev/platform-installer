FROM scratch
COPY rootfs/ /
COPY --chmod=0755 connection-probe /usr/bin/connection-probe
USER 1000:1000
EXPOSE 8080
# The mounted agent.hcl must use env_template and exec /usr/bin/connection-probe.
ENTRYPOINT ["/usr/bin/vault", "agent", "-config=/etc/probe/agent.hcl"]
