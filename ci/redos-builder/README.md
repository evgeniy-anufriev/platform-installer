# Общий сборочный образ RED OS для GitLab

Образ содержит только инструменты сборки: Go 1.26.6, Node.js 24.19.0,
npm 11.17.0, заранее собранную Wails CLI v2.15.0, Python, GCC/G++, pkg-config
и GTK3/WebKit2GTK 4.1 development-библиотеки.

В образе нет исходников приложения, frontend/package.json, package-lock.json,
node_modules, npm-архивов или npm-кэша конкретного проекта. Смена зависимостей
проекта не требует пересборки образа, пока подходит версия инструментов.

База — официальный RED OS UBI 8, закреплённый в Dockerfile по digest.
RPM устанавливаются только из base/updates RED OS с проверкой подписей.
Wails CLI собирается один раз из локального third_party/wails/vendor,
без скачивания Go-модулей. В заданиях GitLab используется готовая CLI.

## Подготовка образа

Из корня обычного распакованного проекта, аналогичного каталогу с go.mod,
frontend, vendor, third_party, build, config и wails.json:

```sh
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

Перейдите в папку с npm_offline.py, portable_source.py, npm-manifest.json и всеми
10 npm-source-*.txt. Укажите фактический путь распакованного проекта в project.
Каталог ~/npm-archives должен быть новым. Команды не используют Интернет:

```sh
python3 - <<'PY'
from pathlib import Path
import npm_offline

project = Path.home() / "platform-installer-restored"
_, records = npm_offline.verify_package(Path.cwd(), project)
output = Path.home() / "npm-archives"
output.mkdir(exist_ok=False)
for record, content in records:
    (output / Path(record["path"]).name).write_bytes(content)
print(f"Готово: {len(records)} .tgz в {output}")
PY
tar -czf "$HOME/npm-deps.tar.gz" -C "$HOME/npm-archives" .
```

Это восстанавливает архивы npm после проверки целостности; исходники приложения
не перепаковываются. Обычные source-*.txt здесь не нужны. Передайте готовый
npm-deps.tar.gz в проект GitLab или как входной artifact. В примере его путь
задаёт переменная NPM_ARCHIVE, по умолчанию это корень checkout.

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
