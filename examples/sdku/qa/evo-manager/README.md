# Evo user-script startup mock

`StartupMock.main(Evo)` prints `SDKU_EVO_MOCK_STARTED` and returns. The actual
evo-manager script loader invokes it. It performs no tag lookups, subscriptions,
CSV reads or Kafka writes. This is a QA input, not the default production script.

Compile on RED OS with the Evo API JAR from the exact selected image:

```sh
java -m jdk.compiler/com.sun.tools.javac.Main -source 17 -target 17 \
  -cp evo-api-1.12.7.jar -d classes src/qa/sdku/StartupMock.java
java -m jdk.jartool/sun.tools.jar.Main --create \
  --file evo-startup-mock.jar -C classes .
```

Place the JAR inside the application package's `assets/qa/`, include it in the
package manifest's `files`, then select it in the application's Files tab:

```yaml
config_files:
  - source: assets/qa/evo-startup-mock.jar
    destination: imitator/lib/evo-startup-mock.jar
    mode: '0644'
environment:
  EVO_MANAGER_MAIN_CLASS: qa.sdku.StartupMock
  EVO_MANAGER_JAR_PATH: /usr/local/app/imitator/lib
  EVO_MANAGER_SOURCE_PATH: ''
  EVO_MANAGER_PACKAGE_WHITE_LIST: qa.sdku
```

Save overrides in the library instance's `group_vars` through the ordinary editor.
The approved library plan copies the original bytes into the instance's `config/`
and mounts them read-only at `/usr/local/app/imitator/lib/evo-startup-mock.jar`.
The Evo image and its API remain unchanged. A successful QA checks the marker
and source/target/container SHA256 on each host, not just container Running.
