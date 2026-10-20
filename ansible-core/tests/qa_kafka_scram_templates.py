"""Native Agent -> environment -> Kafka JAAS parser check; no Vault/Kafka server writes.

Run on RED OS with the already installed Vault and Kafka/JDK runtime.
All credentials in this test are synthetic, never sourced from runtime custody.
"""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collections/ansible_collections/platform/core/plugins/module_utils'))
from application_vault import jaas_field
from kafka_schema_registry import properties_value


class KafkaScramNativeTemplates(unittest.TestCase):
    def test_real_agent_supervisor_renders_java_compatible_quotes(self):
        java, vault = shutil.which('java'), shutil.which('vault')
        self.assertTrue(java and vault, 'Existing Java/Vault runtime is required')
        kafka_home = os.environ.get('KAFKA_HOME', '/opt/kafka')
        self.assertTrue(list(Path(kafka_home, 'libs').glob('kafka-clients-*.jar')))
        password = 'synthetic-"\\-<> &-\n\r\t-кириллица-💠'
        username = 'synthetic-user'
        with tempfile.TemporaryDirectory(prefix='qa-scram-template-') as directory:
            source = Path(directory, 'ScramJaasProbe.java')
            source.write_text('''
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import org.apache.kafka.common.security.JaasContext;
import org.apache.kafka.common.config.types.Password;
import java.util.Map;
class ScramJaasProbe {
  static javax.security.auth.login.AppConfigurationEntry entry(String value) {
    return JaasContext.loadClientContext(Map.of("sasl.jaas.config", new Password(value))).configurationEntries().get(0);
  }
  public static void main(String[] args) throws Exception {
    for (var name : new String[]{"KAFKA_PRODUCER_SASL_JAAS_CONFIG", "KAFKA_CONSUMER_SASL_JAAS_CONFIG"}) {
    if (System.getenv(name) == null) throw new IllegalStateException("ENV_NOT_INJECTED: " + name);
    var actual = entry(System.getenv(name));
    var expected = new String(Base64.getDecoder().decode(System.getenv("EXPECTED_BASE64")), StandardCharsets.UTF_8);
    if (!expected.equals(actual.getOptions().get("password"))
        || !"synthetic-user".equals(actual.getOptions().get("username"))) {
      throw new IllegalStateException("JAAS_QUOTE_MISMATCH");
    }
    }
    var properties = org.apache.kafka.common.utils.Utils.loadProps(args[0]);
    var cliEntry = entry(properties.getProperty("sasl.jaas.config"));
    var cliExpected = new String(Base64.getDecoder().decode(System.getenv("EXPECTED_BASE64")), StandardCharsets.UTF_8);
    if (!cliExpected.equals(cliEntry.getOptions().get("password"))) {
      throw new IllegalStateException("CLI_PROPERTIES_QUOTE_MISMATCH");
    }
    System.out.println("JAAS_NATIVE_PASS");
  }
}
''', encoding='utf-8')
            data = json.dumps({'Data': {'data': {'username': username, 'password': password}}}, ensure_ascii=False)
            cli = Path(directory, 'client.properties')
            cli.write_text('sasl.jaas.config=' + properties_value(
                'org.apache.kafka.common.security.scram.ScramLoginModule required username="synthetic-user" password='
                + json.dumps(password, ensure_ascii=False) + ';') + '\n', encoding='utf-8')
            contents = ('{{ with %s | parseJSON }}org.apache.kafka.common.security.scram.ScramLoginModule required '
                        'username=%s password=%s;{{ end }}') % (json.dumps(data, ensure_ascii=False), jaas_field('username'), jaas_field('password'))
            token = Path(directory, 'synthetic-token')
            token.write_text('synthetic-token')
            token.chmod(0o600)
            class TokenLookup(BaseHTTPRequestHandler):
                def do_GET(self):
                    payload = json.dumps({'data': {'id': 'synthetic-token', 'type': 'service', 'ttl': 3600, 'renewable': False}}).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                def log_message(self, *args):
                    pass
            server = ThreadingHTTPServer(('127.0.0.1', 0), TokenLookup)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            config = ('vault { address = "http://127.0.0.1:%s" }\n'
                      'auto_auth { method "token_file" { config = { token_file_path = %s } } }\n'
                      'listener "unix" { address = %s\n tls_disable = true }\n'
                      'template_config { exit_on_retry_failure = true }\n'
                      'env_template "KAFKA_PRODUCER_SASL_JAAS_CONFIG" { contents = %s\n error_on_missing_key = true }\n'
                      'env_template "KAFKA_CONSUMER_SASL_JAAS_CONFIG" { contents = %s\n error_on_missing_key = true }\n'
                      'exec { command = %s\n restart_on_secret_changes = "never" }\n') % (
                          server.server_port, json.dumps(str(token)), json.dumps(directory+'/agent.sock'),
                          json.dumps('{{/* KAFKA_PRODUCER_SASL_JAAS_CONFIG */}}' + contents, ensure_ascii=False),
                          json.dumps('{{/* KAFKA_CONSUMER_SASL_JAAS_CONFIG */}}' + contents, ensure_ascii=False),
                          json.dumps([java, '-cp', kafka_home+'/libs/*', str(source), str(cli)]))
            path = Path(directory, 'agent.hcl')
            path.write_text(config, encoding='utf-8')
            environment = dict(os.environ, EXPECTED_BASE64=base64.b64encode(password.encode()).decode(), VAULT_TOKEN='')
            with open(Path(directory, 'agent-output.log'), 'w+') as output:
                process = subprocess.Popen([vault, 'agent', '-config='+str(path)], env=environment,
                                           stdout=output, stderr=subprocess.STDOUT, text=True)
                try:
                    deadline = time.monotonic() + 45
                    rendered = ''
                    while time.monotonic() < deadline:
                        output.seek(0)
                        rendered = output.read()
                        if 'JAAS_NATIVE_PASS' in rendered or process.poll() is not None:
                            break
                        time.sleep(.25)
                    self.assertTrue('JAAS_NATIVE_PASS' in rendered, rendered[-1500:])
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    server.shutdown()
                    server.server_close()


if __name__ == '__main__':
    unittest.main()
