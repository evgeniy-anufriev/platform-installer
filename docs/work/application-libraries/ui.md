# Страница «Приложения» — предложение

Владелец предложил новую страницу по образцу существующей страницы «Сервисы».
Это обсуждаемое расширение: текущий UI design относит containers к будущей
application-runtime capability отдельно от инфраструктуры. Макет и production
UI ещё не изменены; визуальная проверка не проводилась.

## Навигация

Список библиотек с экземплярами слева, настройки выбранного элемента справа:

```text
СДКУ (sdku-main)
  apigateway-sdku
  data-manager-sdku
ЦСПА (cspa-main)
  apigateway-cspa
```

Пользователь выбирает пакет и задаёт ID экземпляра библиотеки. ID её приложений
вычисляются как `<application_name>-<library_instance_id>` и показываются
read-only; пути и AppRole identities вручную не дублируются.

## Библиотека

- Общее: название, пакет/версия.
- Подключения: конкретные infra deployments и PKI binding.
- Общие ресурсы: БД/схемы/topics с зависимостями подготовки.
- Общие секреты: source reference, Vault destination, PKI usage; без secret values.
- Приложения: состав и версии экземпляров.
- Размещение: Docker runtime и выбранные хосты; `SERVER_ID` показывается как
  производное от существующего ID хоста, без отдельного поля ввода.

## Экземпляр

- Параметры, image, ports и несекретные env.
- Подключения и УЗ/grants; библиотечные links показываются унаследованными.
- Vault/Agent/AppRole и таблица «переменная → источник → поле → Vault path».
- Файлы конфигурации и mounts.
- Переключатель endpoint, endpoint group, backend settings/health/TLS.
- Findings и revision-bound результаты проверки.

Показывать origin (defaults/библиотека/instance) и действие «Сбросить переопределение».
Не сохранять defaults только из-за открытия формы. Secret values не возвращаются
в snapshot/UI; ввод runtime credentials через существующий отдельный механизм.

Управление reusable packages отделено от редактирования instance: изменение
пакета не должно незаметно менять все экземпляры. Точный package-editor/import
flow пока открыт. Формы строятся по schema/metadata, не hardcoded product logic.

## Сохранение и установка

Использовать существующие guarded writer, Review/Save и Project Verify.
Сама установка остаётся на общей странице «Установка»; план показывает два этапа:
«Инфраструктура» (Apply/Verify всех запланированных сервисов), затем
«Библиотеки приложений». Второй этап ожидает успешного завершения первого.
Внутри библиотеки: подготовка ресурсов → подготовка УЗ/секретов instance → запуск
→ endpoint/verify. При ошибке инфраструктуры показывается причина, по которой
библиотеки не запускались. Порядок и разрешение перехода определяет Core, не UI.
Новый hidden save/start path не вводится. Все mutations проходят fresh plan,
approval и Start. Observed running и externally verified endpoint отображаются раздельно.

До UI реализации сравнить shared rules и affected flows действующих
[UI design](../../design/ui-design-01.md) / [mockups](../../design/ui-design-01-mockups.html), подготовить
конкретный макет и согласовать существенные расхождения. Предложенная структура
не является утверждённым макетом или закрытым UI milestone.
