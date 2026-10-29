# Platform Installer: восстановление, сборка и runtime bundle

Этот комплект содержит исходники приложения, Ansible Core, Go `vendor` и ресурсы
Wails для Windows/Linux, исходники Wails v2.15.0 и зависимости его CLI.
Он состоит из всех частей `source-*.txt`,
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

Для проверки только одной вручную скопированной части достаточно скрипта,
`manifest.json` и выбранного `source-*.txt` в одной папке:

```powershell
python portable_source.py verify-part . source-0001.txt
```

Команда проверяет размер и SHA-256 выбранной части по манифесту. Для v3
применяется нормализация LF/CRLF, для v2 — строгое побайтовое сравнение.
Остальные части не читаются; это не проверка полноты комплекта или возможности
сборки. При успехе выводится `PASS`, при ошибке — причина и код завершения 1.

В Linux откройте терминал в папке комплекта:

```sh
python3 portable_source.py verify .
python3 portable_source.py unpack . "$HOME/installer-restored"
python3 portable_source.py verify . "$HOME/installer-restored"
```

Формат v3 допускает замену LF ↔ CRLF в `source-*.txt`, в том числе при
ручном копировании через Notepad++. Перед проверкой размера, SHA-256 и чтением
записей CRLF однозначно преобразуется в LF. Размеры и хеши частей в манифесте
относятся к этому нормализованному представлению. Лимит 5 000 000 байт
соблюдается и после преобразования всей части в CRLF.

Используйте UTF-8 без BOM для частей. Не меняйте пробелы, символы и количество
строк, не добавляйте и не удаляйте последний перенос: это остаётся ошибкой
контрольной суммы. Одиночный CR не поддерживается. Копируйте весь комплект
одной версии, включая новый `portable_source.py` и `manifest.json`.

`verify` проверяет SHA-256 каждой нормализованной части и восстановленного файла. С дополнительным
аргументом он также сравнивает комплект с восстановленным деревом. Распаковка
сохраняет исходные байты, окончания строк, BOM и права исполнения скриптов.
Обычный текст хранится с LF и признаком исходных LF/CRLF; файлы со смешанными
переносами или одиночным CR сохраняются в Base64. Хеш каждого файла проверяется
после восстановления исходных байтов. Метаданные Git не восстанавливаются.
Старые комплекты v2 по-прежнему читаются строго побайтово: новая устойчивость
к переносам действует только для пересозданных комплектов v3.

## 2. Собрать приложение для Linux

Сборка выполняется непосредственно в Linux. Установленные инструменты должны
включать Go, Node.js, npm, C-компилятор и `pkg-config`. Требования
исходников: Go 1.25+, Node.js >=24.19 и <25, npm 11.17.0.
Нужны development-библиотеки GTK3 и WebKit2GTK с ABI 4.0 или 4.1.
Названия системных пакетов зависят от дистрибутива; смотрите
[требования Wails v2](https://wails.io/docs/gettingstarted/installation/).

Wails CLI заранее устанавливать не требуется: Python build сначала собирает
v2.15.0 из `third_party/wails` в `.runtime/tools/wails`, затем использует именно
этот бинарный файл. Для отдельной сборки CLI и проверки окружения:

```sh
cd "$HOME/installer-restored"
python3 scripts/portable_source.py build-wails .
.runtime/tools/wails doctor
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

Нужны Go 1.25+, Node.js >=24.19 и <25, npm 11.17.0
и штатная Windows-среда Wails. Для запуска приложения требуется WebView2 Runtime.
Предварительная установка Wails CLI не требуется.

Для отдельной сборки Wails CLI и проверки среды:

```powershell
Set-Location C:\work\installer-restored
python scripts/portable_source.py build-wails .
& .\.runtime\tools\wails.exe doctor
```

Сборка:

```powershell
Set-Location C:\work\installer-restored
python scripts/portable_source.py build .
```

Результат: `build\bin\platform-installer-ui.exe`.

Для обеих платформ `build` сначала собирает локальную Wails CLI, затем запускает
`npm ci`, сборку frontend и Wails production build. Зависимости CLI берутся
из `third_party/wails/vendor`, зависимости приложения — из корневого `vendor`.
Обе Go-сборки используют `-mod=vendor`, `GOPROXY=off`, `GOSUMDB=off`,
`GOWORK=off` и `GOTOOLCHAIN=local`: скачивание Go-модулей и toolchain не выполняется.
`go mod tidy` и синхронизация `go.mod` отключены. `npm ci` требует сети или
заранее подготовленного npm-кэша. Go, Node.js и системные development-библиотеки
в текстовый комплект не входят. Wails может обновить генерируемые
`frontend/wailsjs/runtime` при сборке, поэтому сравнивайте восстановленные
исходники с комплектом до сборки. В `third_party/wails/SOURCE.json` зафиксированы
версия, upstream commit и Go module checksums. Сохранены MIT-лицензия Wails,
лицензии зависимостей и обязательные встроенные шаблоны. README-файлы внутри
шаблонов CLI являются ресурсами `go:embed`, а не отдельной документацией проекта.

### 3.1. Собрать Windows EXE на Linux

Способ проверен 2026-10-29 на RED OS 8.0.3 x86_64: комплект v3 восстановлен,
собраны Linux Wails CLI, frontend и Windows EXE. Полученный EXE перенесён на
Windows с проверкой SHA-256; окно `Platform Installer` создано, процесс отвечает,
WebView2 инициализирован. Это проверка сборки и запуска, без визуальной проверки
и установки сервисов.

1. Подготовьте Python 3.8+ и инструменты сборки. Проверенные версии из
   существующих репозиториев RED OS `base`/`updates`: Go 1.26.6, Node.js 24.19.0,
   npm 11.17.0. Для системной установки этих версий:

   ```sh
   sudo dnf install \
     golang-1.26.6-1.red80.x86_64 \
     nodejs-1:24.19.0-1.red80.x86_64 \
     nodejs-npm-1:11.17.0-1.24.19.0.1.red80.x86_64
   ```

   Команда изменяет установленные пакеты системы. При проведённой проверке RPM
   скачивались с зависимостями, проверялись через `rpmkeys --checksig` и
   распаковывались во временную папку без установки. Для сборки Windows EXE
   GTK/WebKit и MinGW не потребовались.

   ```sh
   go version
   node --version
   npm --version
   python3 --version
   ```

2. Поместите `portable_source.py`, `manifest.json` и все `source-*.txt` одной
   версии в `~/installer-package`. Для v3 допускаются LF/CRLF; части сохраняйте
   в UTF-8 без BOM. Проверяйте комплект перед распаковкой:

   ```sh
   cd ~/installer-package
   python3 portable_source.py verify .
   ```

   Ожидается `PASS`. При ручном переносе можно сначала проверить одну часть:

   ```sh
   python3 portable_source.py verify-part . source-0001.txt
   ```

3. Восстановите проект в новую папку и сверьте файлы:

   ```sh
   python3 portable_source.py unpack . ~/installer-restored
   python3 portable_source.py verify . ~/installer-restored
   ```

4. Перейдите в восстановленный проект и задайте окружение:

   ```sh
   cd ~/installer-restored
   export GOFLAGS=-mod=vendor
   export GOPROXY=off
   export GOSUMDB=off
   export GOWORK=off
   export GOTOOLCHAIN=local
   export CGO_ENABLED=0
   ```

   Go использует зависимости из комплекта, без скачивания модулей и toolchain.

5. Соберите локальную Linux Wails CLI из включённых исходников:

   ```sh
   python3 scripts/portable_source.py build-wails .
   .runtime/tools/wails version
   ```

   Ожидается `v2.15.0`; глобальная установка Wails не требуется.

6. Соберите frontend Linux-командами:

   ```sh
   cd frontend
   npm ci --no-audit --no-fund
   npm run build
   cd ..
   ```

   Для `npm ci` нужен доступ к npm registry либо полный подготовленный npm-кэш.

7. Из корня восстановленного проекта соберите Windows EXE:

   ```sh
   .runtime/tools/wails build \
     -platform windows/amd64 \
     -nopackage -clean -m -nosyncgomod -skipbindings -s
   ```

   `-s` пропускает встроенную сборку frontend: она уже выполнена на шаге 6.
   Благодаря этому Windows-команды `npm.cmd` из `wails.json` не вызываются.
   Результат: `build/bin/platform-installer-ui.exe`. Обычная команда
   `python3 scripts/portable_source.py build .` выбирает ОС хоста; для Windows
   из Linux используйте явный `-platform windows/amd64`, как показано выше.

8. Вычислите SHA-256 перед переносом:

   ```sh
   sha256sum build/bin/platform-installer-ui.exe
   ```

   Скопируйте EXE на Windows в ту же структуру проекта: `build/bin/`, сохранив
   рядом с `build/` каталог `config` из восстановленного проекта. Сверьте хеш:

   ```powershell
   Get-FileHash -LiteralPath 'C:\work\installer-restored\build\bin\platform-installer-ui.exe' -Algorithm SHA256
   ```

9. При установленном Microsoft Edge WebView2 Runtime запустите приложение:

   ```powershell
   Set-Location C:\work\installer-restored
   .\build\bin\platform-installer-ui.exe
   ```

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

Каталог `runtime-input` может быть пустым. При подготовке Execution Node уже
установленные prerequisites используются без DNF-транзакции. Недостающие
`python3`, `ansible-core`, `openssl`, `ca-certificates`, `tar`, `gzip` берутся
из совместимого `runtime/packages/OS/VERSION/ARCH` в проверенном bundle.
Пакеты, отсутствующие и на узле, и в bundle, устанавливаются через `dnf install`
из настроенных на узле репозиториев. DNF может обновить уже установленные
зависимости. Если все недостающие prerequisites поставлены локально, репозитории
отключаются; повреждённый RPM или ошибка offline-установки не запускает online retry.
Пустой пакетный payload не обеспечивает полностью автономную свежую установку.
Правила offline-артефактов сервисов остаются прежними.
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

Для пустого входа предварительно создайте каталог, например `mkdir -p /srv/bundle-input`.
Без пакетных платформ сборщик читает `ID`/`VERSION_ID` из `/etc/os-release`
Linux-узла сборки и архитектуру `uname -m`. Для другого целевого узла добавьте
`--platform redos:8.0.3:x86_64` (подставьте его точные значения); параметр можно
повторять. Совместимость сверяется точно, без автоматических алиасов версий.
Подготовка поддерживает RED OS/x86_64 и требует доступных RPM/DNF и sudo.

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

Повторная проверка 2026-10-29: восстановлены и сверены по SHA-256 6545 файлов
из 16 частей. Штатный `build` собрал локальную Wails CLI v2.15.0, frontend
и Windows production EXE. Полученный EXE запущен из восстановленного дерева:
создано окно `Platform Installer`, процесс отвечает, WebView2 сообщил
`Environment created successfully`; через 15 секунд процесс продолжал работу.
Computer Use и визуальная проверка не применялись; установка сервисов не проверялась.

Исправлено выпадение Go-пакета `plumbing/cache` из зависимостей Wails из-за
правила Git `cache/`. Упаковщик сохраняет исходники vendored-зависимостей
независимо от имён каталогов и отклоняет комплект, если в нём отсутствует
пакет, объявленный в одном из двух `vendor/modules.txt`.

Точное восстановление исходников и ресурсов проверено по SHA-256. Windows
frontend/Wails production build из восстановленных файлов прошёл.
Проверка проведена с удалённой из PATH глобальной Wails CLI: локальная CLI
v2.15.0 собрана из исходников и использована для production build приложения.
CLI также кросс-собрана для Linux amd64 с отключённым Go proxy.
Linux-ресурсы включены и восстановлены; сборка самого UI для Linux не запускалась.
Кросс-сборка Windows EXE на Linux и запуск результата на Windows прошли;
пошаговые команды приведены в разделе 3.1.
Runtime bundle в рамках подготовки этого README не собирался и не публиковался:
здесь описаны команды и обязательные входы, сверенные с текущими исходниками.
