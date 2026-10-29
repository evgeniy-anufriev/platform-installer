# Общий сборочный образ RED OS для GitLab

Образ содержит только инструменты сборки: Go 1.26.6, Node.js 24.19.0,
npm 11.17.0, заранее собранную Wails CLI v2.15.0, Python с PyYAML, GCC/G++, pkg-config
и GTK3/WebKit2GTK 4.1 development-библиотеки.

В образе нет исходников приложения, frontend/package.json, package-lock.json,
node_modules, npm-архивов или npm-кэша конкретного проекта. Смена зависимостей
проекта не требует пересборки образа, пока подходит версия инструментов.

База — официальный RED OS UBI 8, закреплённый в Dockerfile по digest.
RPM устанавливаются только из base/updates RED OS с проверкой подписей.
Wails CLI собирается один раз из локального third_party/wails/vendor,
без скачивания Go-модулей. В заданиях GitLab используется готовая CLI.

## Пошаговый порядок

1. Подготовьте обычное дерево проекта и актуальный каталог ci/redos-builder.
2. Преобразуйте npm-source TXT в читаемые tgz и npm-deps.tar.gz по разделу GitLab.
3. Создайте контекст и соберите общий образ без npm-зависимостей проекта.
4. Загрузите образ в Container Registry своего проекта GitLab.
5. Добавьте .gitlab-ci.yml, npm-deps.tar.gz и необходимые статические ресурсы в Git.
6. Подготовьте runtime-input для build-runtime-bundle по разделу ниже.
7. В pipeline вручную запустите frontend-dependencies: после его успеха
   build-windows/build-linux выполнятся автоматически с общим artifact.
   build-runtime-bundle запускается отдельно вручную.

На машине подготовки нужны Docker и Python 3; Go/Node.js/npm устанавливаются
внутри образа. Для CI нужен Linux x86-64/glibc runner с Docker executor,
доступом к репозиторию и Container Registry проекта. Само дерево приложения
должно содержать frontend, vendor, third_party/wails, build, config, internal,
cmd, go.mod, go.sum, корневые Go-файлы и wails.json.

Задайте фактические пути в используемой shell-сессии:

```sh
PROJECT_DIR="$HOME/platform-installer-restored"
NPM_PACKAGE_DIR="$HOME/installer-package"
NPM_ARCHIVES_DIR="$HOME/npm-archives"
```

NPM_PACKAGE_DIR содержит npm_offline.py, portable_source.py, npm-manifest.json
и все 10 npm-source-*.txt одной поставки. NPM_ARCHIVES_DIR должен быть новым.

## Подготовка образа

Из корня обычного распакованного проекта, аналогичного каталогу с go.mod,
frontend, vendor, third_party, build, config и wails.json:

```sh
cd "$PROJECT_DIR"
python3 ci/redos-builder/prepare-context.py . /var/tmp/installer-builder-context
docker build -t platform-installer-builder:redos8 /var/tmp/installer-builder-context
```

Папка контекста должна быть новой. Никаких npm-входов на этом шаге не нужно.
Скрипт копирует только Wails sources/vendor, Dockerfile и build-target.sh;
frontend, node_modules, .runtime/secrets и исходники приложения не копируются.
Сам скрипт работает без Интернета. Сеть при сборке образа нужна только для
официального базового образа и настроенных репозиториев RPM RED OS.
Список установленных RPM находится в /usr/share/wails/builder-rpms.txt.

Если rootless Docker на проверочном node2 не разрешает имена зеркал, можно
передать временные записи только для сборки, без изменения daemon.json:

```sh
set --
for host in repo.red-soft.ru repo1.red-soft.ru mirror.yandex.ru; do
  address=$(getent ahostsv4 "$host" | awk 'NR==1 {print $1}')
  test -n "$address" || exit 1
  set -- "$@" --add-host "$host:$address"
done
docker build "$@" -t platform-installer-builder:redos8 /var/tmp/installer-builder-context
```

HTTPS и проверка подписей RPM остаются включёнными.

Проверка версий в готовом образе без сети:

```sh
docker run --rm --network none platform-installer-builder:redos8 \
  sh -c 'go version; node --version; npm --version; wails version'
```

## Публикация образа в Container Registry GitLab

Подставьте адрес registry и полный путь именно своего проекта, взятые из
Container Registry в GitLab. Значение REGISTRY_IMAGE должно соответствовать
CI_REGISTRY_IMAGE этого проекта, чтобы совпасть с примером CI:

```sh
REGISTRY="registry.example.local"
REGISTRY_IMAGE="$REGISTRY/group/project"
docker login "$REGISTRY"
docker tag platform-installer-builder:redos8 "$REGISTRY_IMAGE/builder:redos8"
docker push "$REGISTRY_IMAGE/builder:redos8"
```

В образе нет npm-архивов проекта. npm-deps.tar.gz передаётся отдельно как
файл репозитория или входной artifact. Runner должен иметь доступ к образу;
если образ размещён по другому пути, задайте BUILDER_IMAGE полным именем.

## Подготовленные зависимости проекта

Вход сборки — обычное дерево проекта с уже подготовленным frontend/node_modules.
Установка npm-зависимостей выполняется отдельным шагом CI из проектного npm-deps.tar.gz, а не при сборке образа.
Скрипт build-installer не вызывает npm ci/npm install и ничего не скачивает.
Если tsc/vite отсутствуют, сборка завершается с понятной ошибкой.

node_modules должен соответствовать lockfile проекта и Linux x86-64/glibc:
именно на Linux запускаются TypeScript/Vite при сборке обеих целей.
node_modules, подготовленный под Windows, macOS, ARM64 или musl, для этого
образа не подходит. Получение зависимостей через Интернет, внутренний registry
или offline-кэш выбирается отдельно на уровне проекта.

## Сборка из обычного дерева проекта

Запускайте из папки проекта, где уже есть frontend/node_modules:

```sh
docker run --rm --pull=never --network none \
  -v "$PWD:/work:Z" platform-installer-builder:redos8 \
  build-installer /work windows/amd64
```

Для Linux UI используйте другой checkout/каталог того же проекта:

```sh
docker run --rm --pull=never --network none \
  -v "$PWD:/work:Z" platform-installer-builder:redos8 \
  build-installer /work linux/amd64
```

Разные каталоги нужны, чтобы сохранить оба результата: Wails очищает build/bin.
Скрипт выполняет npm run build и Wails build с явной целевой платформой.
Go использует vendor и не загружает модули/toolchain; Windows-сборка использует
CGO_ENABLED=0, Linux — CGO_ENABLED=1 и webkit2_41.

Результаты: build/bin/platform-installer-ui.exe или build/bin/platform-installer-ui.
Для Linux также создаётся build/bin/linux-resources с desktop-файлом и иконкой.
Передавайте config рядом с build. Для запуска Windows нужен WebView2 Runtime,
для Linux — графическая сессия и совместимые GTK3/WebKit2GTK runtime-библиотеки.

:Z меняет SELinux-метку подключённого дерева проекта. Для rootless Docker
используется пользователь, владеющий daemon/socket. Для rootful Docker можно
добавить --user "$(id -u):$(id -g)", чтобы результаты принадлежали пользователю.

## GitLab

### Подготовить npm-deps.tar.gz из имеющихся npm-source-*.txt

Используйте пути из начала инструкции. Команды выполняются без Интернета:

```sh
cd "$NPM_PACKAGE_DIR"
python3 - "$PROJECT_DIR" "$NPM_ARCHIVES_DIR" <<'PY'
from pathlib import Path
from urllib.parse import unquote, urlparse
import sys
import npm_offline

project = Path(sys.argv[1])
manifest, records = npm_offline.verify_package(Path.cwd(), project)
_, lock = npm_offline.project_inputs(project)
entries = npm_offline.archives(lock, manifest["npmPlatform"])
exports = {}
for record, content in records:
    url = entries[record["path"]][0]
    parts = unquote(urlparse(url).path).strip("/").split("/")
    name = parts[-1]
    if parts[0].startswith("@"):
        name = parts[0][1:] + "-" + name
    npm_offline.portable.safe_path(name)
    if not name.endswith(".tgz") or name in exports:
        raise ValueError("Invalid/duplicate archive filename: " + name)
    exports[name] = content
output = Path(sys.argv[2])
output.mkdir(parents=True, exist_ok=False)
for name, content in exports.items():
    (output / name).write_bytes(content)
print(f"Готово: {len(exports)} .tgz в {output}")
PY
tar -czf "$PROJECT_DIR/npm-deps.tar.gz" -C "$NPM_ARCHIVES_DIR" .
```

Это восстанавливает архивы npm после проверки целостности; исходники приложения
не перепаковываются. Обычные source-*.txt здесь не нужны. Передайте готовый
npm-deps.tar.gz в проект GitLab или как входной artifact. В примере его путь
задаёт переменная NPM_ARCHIVE, по умолчанию это корень checkout.

Имена читаемые, в стиле [npm pack](https://docs.npmjs.com/cli/v11/commands/npm-pack/):
react-19.2.8.tgz, typescript-6.0.3.tgz, types-node-24.13.3.tgz,
rolldown-binding-linux-x64-gnu-1.2.7.tgz. Для scoped-модулей добавлен scope,
например @types/node → types-node-24.13.3.tgz. Совпадение имён блокируется,
чтобы один архив не перезаписал другой. Меняется только внешнее имя файла;
байты .tgz, npm-source-*.txt, манифесты и integrity из lockfile не меняются.
Команды npm cache add/npm ci ниже подходят и для читаемых, и для хеш-имён.

Если архивы размещаются в registry, их публикация и доставка в задание CI
выполняются отдельно. Эти команды только создают файлы и ничего не публикуют.
В приведённом примере CI входом служит общий npm-deps.tar.gz. Имена файлов
не меняют имя/версию модуля внутри архива и URL в package-lock.json.

### Установка модулей в CI

Из корня checkout, где уже доступен npm-deps.tar.gz:

```sh
mkdir -p .runtime/npm-archives
tar -xzf npm-deps.tar.gz -C .runtime/npm-archives
NPM_CACHE_DIR=$(mktemp -d)
npm cache add --offline --cache "$NPM_CACHE_DIR" --no-audit --no-fund \
  "$PWD"/.runtime/npm-archives/*.tgz
cd frontend
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm ci --offline \
  --cache "$NPM_CACHE_DIR" --no-audit --no-fund
```

npm ci использует подготовленный кэш: напрямую .txt или общий tar.gz он не
читает. Всё это выполняется заданием CI, а не при сборке Docker-образа.

### Задания сборки

Пример gitlab-ci.example.yml принимает npm-deps.tar.gz как вход проекта.
Отдельное задание frontend-dependencies распаковывает архив, наполняет пустой
кэш через npm cache add --offline и явно вызывает npm ci --offline. Затем
frontend/node_modules передаётся двум заданиям компиляции в tar.gz, чтобы
сохранить права и символические ссылки. В самом образе npm-зависимостей нет.

```yaml
include:
  - local: /ci/redos-builder/gitlab-ci.example.yml
```

Этот блок уже записан в корневой .gitlab-ci.yml репозитория. Если pipeline уже есть,
добавьте include и согласуйте его stages со стадиями dependencies/build.
В примере frontend-dependencies явно выполняет npm ci --offline; затем
два задания через needs получают архив node_modules и независимо собирают
Windows/amd64 и Linux/amd64. Переменные Go и CGO задаёт build-installer,
ручной export для задания не нужен.

При push задания сами не запускаются. Нажмите Run у frontend-dependencies:
оно один раз готовит frontend-node-modules.tar.gz, затем build-windows и
build-linux автоматически получают один и тот же artifact. Ошибка подготовки
зависимостей блокирует обе сборки. Все задания находятся в одном pipeline;
скрытые задания и дочерние pipeline не используются.

build-runtime-bundle запускается своей кнопкой Run независимо от UI. Это
необязательное ручное задание (allow_failure: true): отсутствие запуска или
его ошибка не блокирует статус UI-сборок. Результат самого задания нужно
проверять отдельно.

Убедитесь, что каталог ci/redos-builder и npm-deps.tar.gz доступны в checkout.
Для нового репозитория из распакованной папки проверьте статические ресурсы:
/build/bin/ исключён через .gitignore; исходные ресурсы build должны остаться в Git:

```sh
cd "$PROJECT_DIR"
git add ci/redos-builder .gitlab-ci.yml
git add -f npm-deps.tar.gz
git add -f \
  build/appicon.png \
  build/windows/icon.ico \
  build/windows/info.json \
  build/windows/wails.exe.manifest \
  build/linux/build.sh \
  build/linux/icon.png \
  build/linux/platform-installer-ui.desktop
git diff --cached --stat
```

Исходники проекта, frontend/wailsjs, vendor и third_party также должны быть
загружены в GitLab. build/bin, .runtime, секреты и локальный node_modules
коммитить не нужно. После проверки состава коммита выполните git commit/git push
в свой GitLab remote. Для запуска заданий runner должен принимать их tags
либо задания без tags; при необходимости добавьте фактические tags своего runner.

Готовый образ сначала нужно разместить на Docker-host runner или в разрешённом
GitLab Registry. Задайте BUILDER_IMAGE полным именем, предпочтительно с digest.
В примере используется $CI_REGISTRY_IMAGE/builder:redos8.
Docker-in-Docker и privileged для самих заданий компиляции не нужны.

Для переноса готового образа без реестра:

```sh
docker save -o installer-builder-redos8.tar platform-installer-builder:redos8
# После переноса на Docker-host runner:
docker load -i installer-builder-redos8.tar
```

Политика сети реального GitLab Runner задаётся отдельно. В проверке локального
образа компиляция выполняется через docker run --network none.
Реальный pipeline на GitLab Runner и публикация в GitLab Registry не выполнялись.

### Сборка offline Execution Runtime Bundle

Задание `build-runtime-bundle` запускает существующий
`ansible-core/tools/build_execution_runtime_bundle.py` из текущего checkout.
Оно не зависит от npm, Windows EXE или Linux UI. Образ нужно пересобрать с
обновлённым Dockerfile: сборщику bundle требуется пакет RED OS `python3-pyyaml`.
Python-пакеты через pip в CI не загружаются.

До запуска задания предоставьте подготовленный каталог `RUNTIME_INPUT`:
например, через read-only mount Docker executor или artifact отдельного
внутреннего задания подготовки. По умолчанию ожидается
`$CI_PROJECT_DIR/.runtime/runtime-input`. При отсутствии каталога задание
останавливается; оно не скачивает пакеты и не создаёт пустой вход автоматически.
Для artifact из другого задания укажите это задание в `needs` с `artifacts: true`
вместо стандартного `needs: []`.

Пример структуры подготовленного входа:

```text
runtime-input/
├── packages/<os>/<version>/<architecture>/*.rpm
├── python/
└── artifacts/<service>/...
```

Используйте существующие утверждённые runtime-файлы. Для внутреннего каталога,
смонтированного runner в `/build-input/runtime`, задайте в GitLab CI/CD Variables:

```text
RUNTIME_INPUT=/build-input/runtime
```

Версия bundle по умолчанию — `ci-$CI_PIPELINE_IID-$CI_COMMIT_SHORT_SHA`;
её можно изменить переменной `RUNTIME_BUNDLE_VERSION`. Платформы сборщик
определяет по структуре RPM-входа, а при его отсутствии — по ОС Linux-контейнера.
Для другой целевой ОС добавьте к команде сборки явный
`--platform OS:VERSION:ARCH`; для нескольких платформ повторите параметр.
Если нужны записи `containerImages` для архивов приложений, добавьте к этой же
команде повторяемый `--application-image IMAGE artifacts/app.tar`.

Пустой существующий `RUNTIME_INPUT` поддерживается для Core-only bootstrap,
но такой bundle не содержит RPM и сервисных артефактов и не доказывает
возможность полной установки без сети. Полностью автономная установка требует
заранее подготовленного полного набора зависимостей для выбранных сервисов.

После сборки задание компилирует Go CLI из `vendor`, выполняет
`validate-bundle`, затем сохраняет artifacts:

- `.runtime/ci-output/execution-runtime-bundle.tar.gz`;
- `.runtime/ci-output/execution-runtime-bundle.tar.gz.sha256`.

Проверка `validate-bundle` доказывает целостность и структуру bundle, но не
полноту offline-установки. Задание не публикует bundle в активный cache и
не изменяет выбранный Execution Node.

После скачивания обоих artifacts в одну папку:

```sh
sha256sum -c execution-runtime-bundle.tar.gz.sha256
tar -xzf execution-runtime-bundle.tar.gz
# Результат: execution-bundle/manifest.yaml и содержимое bundle.
```

## Получение результатов pipeline

В успешном pipeline скачайте artifacts отдельно из build-windows и build-linux:

- Windows: build/bin/platform-installer-ui.exe и config/;
- Linux: build/bin/platform-installer-ui, build/bin/linux-resources/ и config/.

Сохраняйте config рядом с build. Для запуска EXE на Windows нужен WebView2 Runtime:

```powershell
Set-Location C:\work\installer
.\build\bin\platform-installer-ui.exe
```

Для Linux UI нужны графическая сессия и совместимые GTK3/WebKit2GTK runtime-
библиотеки. Сам файл ELF не содержит эти системные библиотеки.

## Проверка общего образа 2026-10-29

Текущий тег на node2 — platform-installer-builder:redos8, image ID
sha256:f736fa81224c662a01d65d9b4e7583b51e8b58912c03761e5265a28a7836dd91,
размер около 1,64 ГБ. Отсутствие /opt/npm-cache и /opt/builder-inputs проверено.
Windows EXE и Linux ELF собраны из обычных деревьев с подготовленными
node_modules при --network none, без npm ci в заданиях компиляции.
Отсутствие node_modules даёт явную ошибку без попытки установки.

Отдельно проверена цепочка npm-source TXT → 194 tgz → npm-deps.tar.gz →
npm cache add --offline → npm ci --offline в контейнере без сети. Установлены
194 пакета. Передача node_modules в tar.gz сохраняет исполняемые файлы и ссылки.
Сам образ при этом не меняется и не получает зависимости проекта.

Читаемые имена также проверены: 194 архива экспортированы без изменения байтов
и SHA-512, затем npm cache add --offline и npm ci --offline успешно выполнены
в общем сборочном образе с отключённой сетью (установка 194 пакетов за 5 секунд).
