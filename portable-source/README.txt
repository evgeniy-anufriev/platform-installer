Platform Installer: переносимый комплект исходников

Полная пошаговая инструкция, включая сборку и публикацию runtime bundle:
README.md рядом с этим файлом.

Ветка: portable. Базовый commit: 8c9255d28141fe7a202c60831124db2cc7fef841.
Формат: platform-installer-portable-source-v2.
Все части source-*.txt указаны в manifest.json вместе с размерами и SHA-256.
Лимит каждой части: 5000000 байт.
Текстовые файлы хранятся читаемым UTF-8 текстом; двоичные ресурсы — в Base64.

Формат записи:
  @@PORTABLE {JSON с путём, encoding, payloadBytes, индексом блока, SHA-256 и размером файла}
  исходное содержимое или Base64
  @@END
Текстовое содержимое не экранируется: исходники читаются обычным редактором.
Восстановление читает строго payloadBytes байт, поэтому маркеры внутри исходника
не нарушают разбор. Переводы строк, BOM и отсутствие последнего перевода строки
сохраняются байт в байт. Большие файлы делятся на последовательные блоки.
Не меняйте окончания строк в частях: это нарушит проверку SHA-256.
manifest.json содержит порядок, размеры и SHA-256 частей.

Включены Go/React, Ansible Core, vendor, конфигурации, схемы, service packages,
Wails bindings, лицензии зависимостей и ресурсы сборки Windows/Linux,
исходники Wails v2.15.0 в third_party/wails и зависимости CLI в его vendor.
Исключены тесты, документация, QA-скрипты, frontend/dist, node_modules,
runtime/cache/bundle, секреты, RPM и бинарные пакеты Core.
Обязательные ресурсы go:embed в vendor сохранены, включая двоичные файлы Wails.

Требования восстановления: Python 3.8+, только стандартная библиотека.
Переносите все части, manifest.json и portable_source.py вместе.
Команды ниже выполняются из папки portable-source.

Проверка комплекта:
  python portable_source.py verify .

Восстановление в новую папку (папка назначения не должна существовать):
  python portable_source.py unpack . C:\work\installer-restored
  python3 portable_source.py unpack . /home/user/installer-restored

Сравнение восстановленных файлов с комплектом:
  python portable_source.py verify . C:\work\installer-restored
  python3 portable_source.py verify . /home/user/installer-restored

Сборка Windows:
  python portable_source.py build C:\work\installer-restored

Сборка Linux (выполняется на Linux):
  python3 portable_source.py build /home/user/installer-restored
Либо из корня восстановленного проекта:
  sh build/linux/build.sh
Явный выбор WebKit2GTK ABI:
  sh build/linux/build.sh --webkit 4.1
  sh build/linux/build.sh --webkit 4.0

Нужны Go (go.mod: 1.25+), Node >=24.19 и <25, npm 11.17.0.
Устанавливать Wails CLI не нужно: build сначала собирает ее из исходников
в .runtime/tools/wails.exe (Windows) или .runtime/tools/wails (Linux).
Отдельная сборка CLI: python scripts/portable_source.py build-wails .
В Linux используйте python3. Эта команда выполняется из корня проекта.
На Linux также нужны C-компилятор, pkg-config, GTK3 и WebKit2GTK dev-библиотеки.
Скрипт проверяет pkg-config и предпочитает ABI 4.1, добавляя -tags webkit2_41;
если доступен только ABI 4.0, используется стандартная сборка Wails.
Официальные требования: https://wails.io/docs/gettingstarted/installation/

Ресурсы Linux:
  build/linux/build.sh — запуск Python build из любой текущей папки;
  build/linux/icon.png — иконка приложения;
  build/linux/platform-installer-ui.desktop — ярлык для рабочего окружения.
После сборки ярлык и иконка копируются в build/bin/linux-resources.
Ярлык использует Exec=platform-installer-ui и Icon=platform-installer-ui;
для установки нужно разместить бинарный файл в PATH, ярлык в каталоге
applications, а иконку — в стандартном каталоге иконок. Скрипт их не устанавливает.

Сборка запускает локальную сборку Wails CLI, npm ci, frontend build и Wails
production build с GOFLAGS=-mod=vendor и отключенными GOPROXY/GOSUMDB,
без go mod tidy/синхронизации go.mod и без перегенерации Go bindings.
npm ci требует доступных npm-пакетов: сеть либо подготовленный кэш.
Это исходники, а не автономный комплект инструментов или runtime bundle.
Core/Python/Ansible скрипт build не запускает.
Результат Windows: build/bin/platform-installer-ui.exe.
Результат Linux: build/bin/platform-installer-ui.

Повторная упаковка текущих исходников Git worktree:
  python portable_source.py pack C:\path\platform-installer-v2 C:\work\new-package
  python3 portable_source.py pack /home/user/project /home/user/new-package
Упаковка берет текущие байты отслеживаемых файлов и дополнительно включает
scripts/portable_source.py, семь Wails build-ресурсов Windows/Linux и дерево
third_party/wails с CLI-зависимостями. Обязательные README внутри go:embed
шаблонов Wails сохранены как ресурсы CLI.
Выходная папка должна быть новой. Для упаковки нужен Git; для восстановления — нет.
Другие неотслеживаемые файлы автоматически не включаются.

Проверено 2026-10-13:
- все файлы восстановлены с точным совпадением SHA-256 до сборки;
- лимит 5 MB и читаемость текстовых исходников подтверждены;
- Unicode, CRLF, маркеры внутри текста, пустые файлы и двоичные ресурсы восстановлены;
- поврежденный комплект и существующая папка назначения отклоняются;
- Windows frontend/Wails production build из восстановленных файлов PASS;
- сборка Windows проверена без глобальной Wails CLI в PATH;
- Wails CLI кросс-сборка Linux amd64 без Go proxy PASS;
- ресурсы Linux восстановлены; сборка на Linux не запускалась.
Wails при сборке обновляет свои генерируемые frontend/wailsjs/runtime файлы
даже с -skipbindings; после сборки они могут отличаться от исходного комплекта.
npm ci сообщил 2 high severity findings в текущем зафиксированном дереве зависимостей.
Зависимости не обновлялись. Реальный UI и установка сервисов не проверялись.
