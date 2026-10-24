#!/bin/sh
set -eu
: "${JAVA_KEYSTORE_PASSWORD:?JAVA_KEYSTORE_PASSWORD is required}"
exec java \
  -Djavax.net.ssl.trustStore=/opt/application/pki/truststore.p12 \
  -Djavax.net.ssl.trustStoreType=PKCS12 \
  "-Djavax.net.ssl.trustStorePassword=$JAVA_KEYSTORE_PASSWORD" \
  "$@"
