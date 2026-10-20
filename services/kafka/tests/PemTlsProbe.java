import java.io.*;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import javax.net.ssl.*;
import org.apache.kafka.common.config.ConfigDef;
import org.apache.kafka.common.config.SslConfigs;
import org.apache.kafka.common.security.ssl.DefaultSslEngineFactory;
import io.confluent.kafka.schemaregistry.rest.SchemaRegistryConfig;
import io.confluent.rest.SslFactory;

/** Synthetic loopback TLS only; never starts Kafka or Schema Registry services. */
class PemTlsProbe {
  static Properties select(Properties source, String prefix) {
    Properties result = new Properties();
    source.forEach((k, v) -> { if (k.toString().startsWith(prefix)) {
      result.put(k.toString().substring(prefix.length()), v);
    }});
    return result;
  }
  static DefaultSslEngineFactory kafka(Properties values) {
    ConfigDef definition = new ConfigDef();
    SslConfigs.addClientSslSupport(definition);
    DefaultSslEngineFactory factory = new DefaultSslEngineFactory();
    factory.configure(definition.parse(values));
    return factory;
  }
  static void handshake(SSLContext serverContext, SSLContext clientContext) throws Exception {
    try (SSLServerSocket server = (SSLServerSocket) serverContext.getServerSocketFactory()
        .createServerSocket(0, 8, InetAddress.getByName("127.0.0.1"))) {
      server.setNeedClientAuth(true);
      server.setSoTimeout(10000);
      ExecutorService executor = Executors.newSingleThreadExecutor();
      Future<?> response = executor.submit(() -> {
        try (SSLSocket socket = (SSLSocket) server.accept()) {
          socket.setSoTimeout(10000);
          socket.startHandshake();
          if (socket.getInputStream().read() != 37) throw new IOException("TLS_PAYLOAD");
          socket.getOutputStream().write(42);
        } catch (Exception e) { throw new RuntimeException(e); }
      });
      try (SSLSocket client = (SSLSocket) clientContext.getSocketFactory()
          .createSocket("localhost", server.getLocalPort())) {
        client.setSoTimeout(10000);
        SSLParameters parameters = client.getSSLParameters();
        parameters.setEndpointIdentificationAlgorithm("HTTPS");
        client.setSSLParameters(parameters);
        client.startHandshake();
        client.getOutputStream().write(37);
        if (client.getInputStream().read() != 42) throw new IOException("TLS_RESPONSE");
        response.get(15, TimeUnit.SECONDS);
      } finally { executor.shutdownNow(); }
    }
  }
  public static void main(String[] args) throws Exception {
    String mode = args[0];
    String path = args[1];
    Properties properties = new Properties();
    try (InputStream input = Files.newInputStream(Path.of(path))) { properties.load(input); }
    if (mode.equals("registry")) {
      SchemaRegistryConfig config = new SchemaRegistryConfig(properties);
      var https = SslFactory.createSslContextFactory(config.getBaseSslConfig());
      https.start();
      try (var client = kafka(select(properties, "kafkastore."))) {
        handshake(https.getSslContext(), client.sslContext());
      } finally { https.stop(); }
    } else {
      Properties selected = mode.equals("broker")
          ? select(properties, "listener.name.internal.") : properties;
      try (var factory = kafka(selected)) { handshake(factory.sslContext(), factory.sslContext()); }
    }
    System.out.println("PEM_TLS_NATIVE_PASS " + mode);
  }
}
