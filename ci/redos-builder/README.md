# Сборочный образ RED OS для GitLab

Образ предназначен для обычного распакованного проекта с `go.mod`, `vendor`,
`third_party/wails`, `frontend`, `build`, `config` и `wails.json`.
В заданиях CI не используются `source-*.txt`, `npm-source-*.txt` или скрипты
распаковки portable-source.

## Состав

- Официальный [RED OS UBI 8](https://redos.red-soft.ru/base/redos-8_0/8_0-administation/8_0-containers/8_0-docker-install/),
  закреплённый в Dockerfile по digest.
- Go 1.26.6, Node.js 24.19.0, npm 11.17.0, Python, GCC/G++, pkg-config,
  GTK3/WebKit2GTK 4.1 development-библиотеки из `base`/`updates` RED OS.
  DNF проверяет подписи RPM.
- Wails CLI v2.15.0, заранее собранная из `third_party/wails` и её vendor,
  без загрузки Go-модулей. В заданиях Wails повторно не компилируется.
- Локальный npm-кэш для текущих package.json/package-lock.json, заполненный
  проверенными архивами. Архивы для чужих необязательных платформ не включаются.
  Смена package.json/lockfile требует пересборки образа; job остановится явно,
  без загрузки зависимостей из Интернета.

Образ и задания рассчитаны на Linux x86-64/glibc. Он собирает Windows/amd64
EXE и Linux/amd64 UI. Для запуска Linux UI на целевой машине нужны совместимые
GTK3/WebKit2GTK runtime-библиотеки; графическая сессия не нужна для компиляции.

## Подготовка и сборка образа

На машине подготовки нужны Docker, Python 3 и обычное дерево проекта. Каталог
`ci/redos-builder` должен быть скопирован в проект или присутствовать в Git.
Отдельно подготовьте каталог с проверенными npm `.tgz`-архивами: имена файлов
должны быть SHA-512 в hex с расширением `.tgz`, как в ранее подготовленных
offline-входах. Это вход подготовки образа, а не вход заданий GitLab.

```sh
cd /path/to/platform-installer
python3 ci/redos-builder/prepare-context.py \
  . /srv/build-input/npm-tarballs /var/tmp/installer-builder-context
docker build -t platform-installer-builder:redos8 /var/tmp/installer-builder-context
```

Папка контекста должна быть новой. Подготовщик проверяет SHA-512 архивов по
lockfile и копирует только Wails sources/vendor, npm-архивы, два frontend
манифеста, Dockerfile и build-target.sh. `.runtime/secrets`, конфигурация Docker,
пользовательские данные и исходники всего приложения в контекст не попадают.
Архивы npm он не скачивает; отсутствие нужного архива — ошибка подготовки.

Во время сборки образа сеть нужна только для официального базового образа
и настроенных репозиториев RPM RED OS. `npm cache add` работает с локальными
архивами через `--offline`. Устанавливаемые RPM и их версии записываются
в `/usr/share/wails/builder-rpms.txt` готового образа.

Пакеты ОС/Go/Node.js/npm приходят из RED OS, Wails — из локальных исходников,
а npm-зависимости приложения — из отдельно предоставленных архивов lockfile.
Скачивания из npm registry при подготовке этого контекста, сборке образа
и компиляции приложения не выполняются.

На проверочном node2 у rootless Docker не работал DNS внутри контейнеров.
Применялся временный обход только для операции сборки, без изменения daemon.json:

```sh
set --
for host in repo.red-soft.ru repo1.red-soft.ru mirror.yandex.ru; do
  address=$(getent ahostsv4 "$host" | awk 'NR==1 {print $1}')
  test -n "$address" || exit 1
  set -- "$@" --add-host "$host:$address"
done
docker build "$@" -t platform-installer-builder:redos8 /var/tmp/installer-builder-context
```

Если DNS контейнеров работает, дополнительные параметры не нужны. HTTPS и
проверка подписей RPM остаются включёнными в обоих вариантах.

## Сборка приложения без сети

Команды запускаются из обычного дерева проекта, аналогичного checkout GitLab.
Они создают/обновляют `frontend/node_modules` и `build/bin` в этом дереве:

```sh
docker run --rm --pull=never --network none \
  -v "$PWD:/work:Z" platform-installer-builder:redos8 \
  build-installer /work windows/amd64

docker run --rm --pull=never --network none \
  -v "$PWD:/work:Z" platform-installer-builder:redos8 \
  build-installer /work linux/amd64
```

`:Z` нужен на SELinux-хостах и меняет метку только подключённого дерева проекта.
Для rootless Docker используется обычный пользователь, владеющий daemon/socket.
Для rootful Docker можно добавить `--user "$(id -u):$(id -g)"`, чтобы результаты
принадлежали текущему пользователю. Для независимого хранения обоих результатов
используйте разные checkout/каталоги: Wails очищает `build/bin` перед сборкой.

Результаты:

- Windows: `build/bin/platform-installer-ui.exe`;
- Linux: `build/bin/platform-installer-ui` и `build/bin/linux-resources/`.

Для передачи приложения сохраняйте `config/` рядом с `build/`. При запуске
Windows EXE нужны WebView2 Runtime, при запуске Linux UI — графическая сессия
и совместимые GTK/WebKit runtime-библиотеки.

## GitLab

`gitlab-ci.example.yml` содержит два независимых задания для Docker executor:
каждое собирает обычный checkout и сохраняет бинарный файл с config в artifacts.
Пример можно подключить из корневого `.gitlab-ci.yml`:

```yaml
include:
  - local: /ci/redos-builder/gitlab-ci.example.yml
```

Перед первым запуском администратор сборочной среды должен загрузить готовый
образ в реестр GitLab и задать `BUILDER_IMAGE` его полным именем, предпочтительно
с digest. В примере используется `$CI_REGISTRY_IMAGE/builder:redos8`.
Это обычный job image: Docker-in-Docker и privileged для заданий компиляции
не требуются. Docker нужен только на этапе подготовки/публикации образа.

В примере Go/npm загрузки отключены переменными и `npm ci --offline`.
Физическая изоляция сети в реальном GitLab настраивается на стороне runner;
она не включается произвольным полем в YAML задания. Проверка этого образа
проводится отдельно через `docker run --network none`.

Готовый образ можно перенести между изолированными Docker-хостами обычным файлом:

```sh
docker save -o installer-builder-redos8.tar platform-installer-builder:redos8
# На сборочном хосте GitLab после переноса файла:
docker load -i installer-builder-redos8.tar
```

Для Docker executor образ должен быть доступен daemon соответствующего runner
либо в разрешённом реестре. Загрузка образа на рабочую станцию сама по себе
не размещает его на другом runner.

## Выполненная проверка 2026-10-29

- Образ собран на RED OS 8.0.3 через rootless Docker без изменения настроек
  daemon и существующих сервисных контейнеров. Размер около 1,67 ГБ.
- Локальный проверенный тег на node2: `platform-installer-builder:redos8`.
  Image ID: `sha256:3f163eae2abe25a4b288a11a2dcc1c0b2262e5215aa578f5443bb69ed0742603`.
- Оба задания собрали обычные деревья проекта без portable-source и без
  исходного frontend/node_modules. Сеть отключена через `docker run --network none`;
  контрольное соединение возвращало `Network is unreachable`.
- Windows/amd64: EXE построен; перенесён на Windows с совпадением SHA-256,
  создано окно Platform Installer, процесс отвечает, WebView2 инициализирован.
- Linux/amd64: ELF построен с `webkit2_41`, отсутствующих библиотек в ldd нет.
  Графический запуск Linux UI отдельно не проверялся.
- Проверена блокировка устаревшего lockfile: задание завершилось до npm ci,
  без загрузки зависимостей и без создания node_modules.
- Команды и пути artifacts из примера GitLab проверены; реальный pipeline
  на GitLab Runner и публикация образа в GitLab Registry не выполнялись.
