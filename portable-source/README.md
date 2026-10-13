# Platform Installer: восстановление, сборка и runtime bundle

Этот комплект содержит исходники приложения, Ansible Core, Go `vendor` и ресурсы
Wails для Windows/Linux. Он состоит из `source-0001.txt` … `source-0006.txt`,
`manifest.json` и `portable_source.py`. Каждая текстовая часть не превышает
5 000 000 байт. Текстовые исходники читаемы; двоичные ресурсы используют Base64.
Тесты, документация, кэши, секреты, RPM и бинарные пакеты Core исключены.

## 1. Распаковать проект

Нужен Python 3.8 или новее. Дополнительные Python-пакеты для восстановления
не требуются. Скопируйте все части, манифест и скрипт в одну папку.
Папка назначения должна быть новой: скрипт отказывается перезаписывать проект.

В Windows откройте PowerShell в папке комплекта:

```powershell
python portable_source.py verify .
python portable_source.py unpack . C:\work\installer-restored
python portable_source.py verify . C:\work\installer-restored
```

В Linux откройте терминал в папке комплекта:

```sh
python3 portable_source.py verify .
python3 portable_source.py unpack . "$HOME/installer-restored"
python3 portable_source.py verify . "$HOME/installer-restored"
```

`verify` проверяет SHA-256 каждой части и каждого файла. С дополнительным
аргументом он также сравнивает комплект с восстановленным деревом. Распаковка
сохраняет байты, окончания строк, BOM и права исполнения скриптов. Не меняйте
окончания строк в текстовых частях. Метаданные Git не восстанавливаются.

## 2. Собрать приложение для Linux

Сборка выполняется непосредственно в Linux. Установленные инструменты должны
включать Go, Node.js, npm, Wails CLI, C-компилятор и `pkg-config`. Требования
исходников: Go 1.25+, Node.js >=24.19 и <25, npm 11.17.0, Wails CLI v2.15.0.
Нужны development-библиотеки GTK3 и WebKit2GTK с ABI 4.0 или 4.1.
Названия системных пакетов зависят от дистрибутива; смотрите
[требования Wails v2](https://wails.io/docs/gettingstarted/installation/).

Если Wails CLI ещё не установлен, в разрешённой среде разработки с доступом
к зависимостям установите именно версию проекта:

```sh
go install github.com/wailsapp/wails/v2/cmd/wails@v2.15.0
export PATH="$(go env GOPATH)/bin:$PATH"
wails doctor
```

Соберите восстановленный проект:

```sh
cd "$HOME/installer-restored"
sh build/linux/build.sh
```

Скрипт определяет доступный WebKit2GTK через `pkg-config`: предпочитает 4.1
и добавляет `-tags webkit2_41`, иначе использует 4.0. Можно выбрать ABI явно:

```sh
sh build/linux/build.sh --webkit 4.1
# Либо, если установлены development-библиотеки ABI 4.0:
sh build/linux/build.sh --webkit 4.0
```

То же самое напрямую через Python:

```sh
python3 scripts/portable_source.py build . --webkit 4.1
```

Результат: `build/bin/platform-installer-ui`. Рядом в `build/bin/linux-resources/`
появятся `.desktop`-ярлык и иконка. Скрипт не устанавливает их в систему.
Для использования ярлыка бинарный файл должен быть доступен как
`platform-installer-ui` через `PATH`, а иконка — под именем `platform-installer-ui`
в стандартном каталоге иконок. GTK3/WebKit2GTK runtime-библиотеки нужны и при запуске.

## 3. Собрать приложение для Windows

Нужны Go 1.25+, Node.js >=24.19 и <25, npm 11.17.0, Wails CLI v2.15.0
и штатная Windows-среда Wails. Для запуска приложения требуется WebView2 Runtime.
Проверьте среду через `wails doctor`.

При необходимости установите Wails CLI в разрешённой среде разработки:

```powershell
go install github.com/wailsapp/wails/v2/cmd/wails@v2.15.0
$env:Path = "$(go env GOPATH)\bin;$env:Path"
wails doctor
```

Сборка:

```powershell
Set-Location C:\work\installer-restored
python scripts/portable_source.py build .
```

Результат: `build\bin\platform-installer-ui.exe`.

Для обеих платформ `build` запускает `npm ci`, сборку frontend и Wails
production build. Go-зависимости берутся из `vendor` с `GOFLAGS=-mod=vendor`;
`go mod tidy` и синхронизация `go.mod` отключены. `npm ci` требует сети или
заранее подготовленного npm-кэша. Wails CLI и системные development-библиотеки
в текстовый комплект не входят. Wails может обновить генерируемые
`frontend/wailsjs/runtime` при сборке, поэтому сравнивайте восстановленные
исходники с комплектом до сборки.

## 4. Подготовить входы для runtime bundle

Runtime bundle — отдельный immutable каталог для подготовки Execution Node и
работы Core. Бинарный файл desktop-приложения в него не входит.
Текстового экспорта недостаточно: RPM, offline Python-пакеты и сервисные
артефакты нужно передать отдельно из проверенного, одобренного источника.
Сборщик ничего не скачивает.

Сборка Core/bundle выполняется в доверенной Linux-среде с уже существующим
Python/Core runtime и его зависимостями, включая PyYAML. Windows используется
для Go-проверки и публикации готового bundle, но не для запуска Core/Python
сборщика. Для существующего SI11 окружения узел сборки — node2,
`192.168.56.102`; выбранный узел установки node1 не используется для bootstrap
собственного runtime. При удалённой работе используйте существующую доверенную
SSH identity и строгую проверку `known_hosts`.

Перенесите текущие восстановленные исходники в отдельную папку доверенного
узла. Дальнейшие команды выполняются из корня именно этой версии исходников.
Python-интерпретатор в примере `python3` должен относиться к уже подготовленной
среде Core; если используется готовая venv, укажите её интерпретатор вместо него.

Подготовьте отдельную папку `runtime-input`, например `/srv/bundle-input`, с
проверенным runtime payload:

```text
runtime-input/
  packages/<os>/<version>/<architecture>/  # Полная необходимая локальная пакетная closure
  python/                                # Проверенный offline Python/Ansible payload
  artifacts/<service>/                    # Необходимые сервисные артефакты
```

Сохраните исходную структуру runtime payload. `packages/` и `python/` обязательны,
а в `packages/` должна быть хотя бы одна непустая платформа. Для требуемых
сервисов добавьте точные версии и SHA-256 из их `artifacts.yml` и каталога;
название файла само по себе совместимость не доказывает. Сборщик формирует
artifact index только для совпадающих метаданных и содержимого. Успешная
структурная проверка bundle не доказывает полноту артефактов для любого
произвольного deployment: проверьте closure под выбранные сервисы/платформы.

Если входные пакеты отсутствуют, сначала получите их через отдельно разрешённое
DEV acquisition. PROD не скачивает из Интернета и не меняет поставленный bundle.
Не включайте runtime-секреты, ключи или пароли в `runtime-input`.

## 5. Собрать runtime bundle на Linux

Замените входной путь и версию своими значениями. Выходной каталог должен быть
новым; повторная сборка в существующий каталог отклоняется.

```sh
cd "$HOME/installer-restored"
mkdir -p .runtime/artifacts
python3 ansible-core/tools/build_execution_runtime_bundle.py \
  --runtime-input /srv/bundle-input \
  --output .runtime/artifacts/portable-20261013-01 \
  --bundle-version portable-20261013-01 \
  --core-version 0.1.0
```

Сборщик добавляет текущие `ansible-core`, `services`, `contracts`, каталог
`examples/catalog` и заданный runtime payload, затем формирует `manifest.yaml`
с digest и component checksums. Для новой поставки используйте новую версию
bundle. `core-version` должен соответствовать вашей поставке Core.

## 6. Проверить и опубликовать bundle

Используйте штатную CLI из этих же исходников. Она отдельна от Wails UI и
собирается без GTK/WebKit и без предварительной сборки frontend.

### В Linux

Из корня восстановленного проекта:

```sh
mkdir -p build/bin
go build -mod=vendor -o build/bin/platform-installer-cli ./cmd/platform-installer
build/bin/platform-installer-cli -command validate-bundle \
  -bundle .runtime/artifacts/portable-20261013-01
```

После успешной проверки сохраните предыдущий bundle, если он ещё нужен, в
отдельном согласованном staging/QA-кэше. Публикация заменяет активный локальный
bundle и удаляет предыдущий digest из указанного `cache/`.

```sh
build/bin/platform-installer-cli -command publish-bundle \
  -bundle .runtime/artifacts/portable-20261013-01 \
  -cache cache
```

### В Windows

Передайте весь каталог bundle с Linux-узла в
`C:\work\installer-restored\.runtime\artifacts\portable-20261013-01`,
сохранив байты и структуру. Затем из корня восстановленного проекта:

```powershell
New-Item -ItemType Directory -Force build\bin | Out-Null
go build -mod=vendor -o build\bin\platform-installer-cli.exe ./cmd/platform-installer
& .\build\bin\platform-installer-cli.exe -command validate-bundle `
  -bundle .runtime\artifacts\portable-20261013-01
```

Продолжайте только после успешного завершения проверки:

```powershell
& .\build\bin\platform-installer-cli.exe -command publish-bundle `
  -bundle .runtime\artifacts\portable-20261013-01 `
  -cache cache
```

Указывайте именно активный `cache/` экземпляра Installer, который будет
использовать bundle. Путь `cache` в примерах относится к текущему каталогу.
Не заменяйте публикацию ручным копированием в `cache/`. Штатный publisher
повторно проверяет bundle и возвращает опубликованный digest.

Публикация означает размещение в локальном immutable `cache/<digest>/`, а не
загрузку в Интернет. Для поставки заказчику передайте весь проверенный каталог
bundle через разрешённый канал. В существующем проекте штатный UI поддерживает
импорт из точной подпапки `<project>/bundle/` через «Обновить набор установки»
и «Привязать». Это источник импорта, а не ручная замена активного cache.

После публикации/привязки сверьте возвращённый digest с bundle lock проекта,
перезапустите Installer и при необходимости заново подготовьте Execution Node.
Для установки всегда нужен новый authoritative Plan, его approval и Start.
Сборка/публикация bundle сами по себе установку не запускают.

## 7. Проверки этого комплекта

Точное восстановление исходников и ресурсов проверено по SHA-256. Windows
frontend/Wails production build из восстановленных файлов прошёл.
Linux-ресурсы включены и восстановлены; Linux Wails-сборка не запускалась.
Runtime bundle в рамках подготовки этого README не собирался и не публиковался:
здесь описаны команды и обязательные входы, сверенные с текущими исходниками.
