import { useEffect, useMemo, useState } from "react";
import type {
  EditResult,
  InstallationEventView,
  ManagedProjectView,
} from "./backend";
import { eventTimestampLabel, taskNameWithoutRole } from "./event-format";
import "./utility-pages.css";

type HelpPageId =
  | "project"
  | "servers"
  | "topology"
  | "services"
  | "certificates"
  | "installation"
  | "logs";

type HelpArticle = {
  id: string;
  title: string;
  summary: string;
  intro: string;
  sections: { title: string; steps?: string[]; text?: string }[];
  warning?: string;
  targetPage?: HelpPageId;
};

const helpCategories = [
  {
    id: "project",
    title: "Проект и набор",
    description: "Создание, сохранение и совместимость набора установки.",
  },
  {
    id: "servers",
    title: "Серверы",
    description: "Подключение к серверам и подготовка узла выполнения.",
  },
  {
    id: "services",
    title: "Сервисы и топология",
    description: "Настройки сервисов, роли и размещение.",
  },
  {
    id: "certificates",
    title: "Сертификаты",
    description: "Профили PKI, проверка имён и пароль Java-хранилищ.",
  },
  {
    id: "installation",
    title: "Проверка и установка",
    description: "Проверка проекта, план и выполнение.",
  },
  {
    id: "logs",
    title: "Журналы",
    description: "Поиск событий и чтение результата запуска.",
  },
  {
    id: "errors",
    title: "Ошибки",
    description: "Причины блокировок и безопасные шаги восстановления.",
  },
] as const;

const helpPageLabels: Record<HelpPageId, string> = {
  project: "Проект",
  servers: "Серверы",
  topology: "Топология",
  services: "Сервисы",
  certificates: "Сертификаты",
  installation: "Установка",
  logs: "Журналы",
};

const helpArticles: (HelpArticle & {
  category: (typeof helpCategories)[number]["id"];
})[] = [
  {
    id: "certificate-authority-settings",
    category: "certificates",
    title: "Управляемые центры сертификации",
    summary:
      "Что задаётся в форме редактирования центра и как он связан с профилем сертификата.",
    intro:
      "Центр сертификации — исходная точка цепочки PKI. В текущем интерфейсе поддерживается управляемый центр; созданный центр выбирается в профиле сертификата.",
    sections: [
      {
        title: "Поля формы «Изменить»",
        steps: [
          "ID — уникальный идентификатор центра; у существующей записи он недоступен для изменения.",
          "Отображаемое имя — необязательная подпись в интерфейсе.",
          "Общее имя (CN) — обязательное имя центра в субъекте сертификата.",
          "Срок действия (дней) — необязательное переопределение; пустое значение наследуется.",
        ],
      },
      {
        title: "После изменения",
        text: "Изменение добавляется в черновик проекта. Сохраните проект и запустите проверку Core, чтобы проверить итоговую конфигурацию.",
      },
    ],
    targetPage: "certificates",
  },
  {
    id: "certificate-profile-settings",
    category: "certificates",
    title: "Профили сертификатов",
    summary:
      "Как редактировать алгоритм и назначение ключа, правила SAN и поля субъекта.",
    intro:
      "Профиль сертификата связывает центр сертификации с параметрами выпуска. На него ссылаются TLS-профили и области применения.",
    sections: [
      {
        title: "Основные поля формы",
        steps: [
          "ID — уникальный идентификатор профиля; для существующей записи он фиксирован. Отображаемое имя необязательно.",
          "Центр сертификации — обязательная ссылка на существующую запись.",
          "Алгоритм ключа — RSA или EC; пустое значение наследует настройку роли.",
          "Размер ключа и срок действия в днях — необязательные переопределения.",
          "Назначение сертификата — отметьте серверную и/или клиентскую аутентификацию.",
        ],
      },
      {
        title: "Правила SAN и субъект",
        text: "Для DNS-имён серверов, IP-адресов серверов, FQDN и wildcard-имён точек входа, а также виртуальных IP можно выбрать «Наследуется», «Включено» или «Выключено». Поля субъекта C, ST, L, O и OU задают необязательные переопределения страны, региона, города, организации и подразделения. Оставляйте наследование, если проекту не требуется явное значение.",
      },
    ],
    warning:
      "Правила SAN являются настройкой профиля. Фактические имена сертификатов рассчитывает и показывает Core после проверки сохранённого проекта.",
    targetPage: "certificates",
  },
  {
    id: "certificate-tls-settings",
    category: "certificates",
    title: "Профили TLS",
    summary:
      "Как связать профиль сертификата с областью и ссылкой на runtime-секрет.",
    intro:
      "Профиль TLS связывает профиль сертификата с параметрами использования TLS. Его можно назначить сервису или использовать при настройке области применения.",
    sections: [
      {
        title: "Поля формы «Изменить»",
        steps: [
          "ID — уникальный идентификатор профиля TLS; у существующей записи его нельзя изменить.",
          "Профиль сертификата — обязательная ссылка на созданный профиль сертификата.",
          "Область применения — «Наследуется», «Сервер», «Экземпляр» или «Развёртывание».",
          "Ссылка на runtime-секрет — укажите ссылку на секрет пароля хранилища; сам пароль здесь не вводится.",
        ],
      },
      {
        title: "Безопасность секрета",
        text: "В проект сохраняется ссылка, а не значение пароля. Уже сохранённая ссылка не показывается как пароль; чтобы заменить её, введите новую ссылку.",
      },
    ],
    targetPage: "certificates",
  },
  {
    id: "certificate-scope-settings",
    category: "certificates",
    title: "Области применения сертификатов",
    summary:
      "Как выбрать профиль, целевые серверы и сервисы и добавить явные DNS/IP.",
    intro:
      "Область применения указывает, где использовать профиль сертификата и откуда собирать идентичности. Источники выбираются из серверов и размещённых сервисов текущего черновика.",
    sections: [
      {
        title: "Поля формы «Изменить»",
        steps: [
          "ID — уникальный идентификатор области; существующий ID фиксирован. Отображаемое имя необязательно.",
          "Профиль сертификата — обязательная ссылка на профиль.",
          "Область применения — наследуемая, для сервера, экземпляра или развёртывания.",
          "В списках «Серверы», «Развёртывания» и «Экземпляры» отметьте необходимые источники. Экземпляр обозначен парой «развёртывание/экземпляр».",
          "При необходимости укажите явные DNS-имена и IP-адреса; несколько значений можно разделить запятыми или переносами строк.",
        ],
      },
      {
        title: "Если список пуст",
        text: "Нет доступных записей, когда соответствующих серверов или размещённых экземпляров нет в текущем черновике. Сначала настройте серверы или размещение сервиса, затем вернитесь к области применения.",
      },
    ],
    warning:
      "Явные DNS/IP дополняют источники области. Итоговые имена и SAN проверьте в блоке «Проверка Core» после сохранения проекта.",
    targetPage: "certificates",
  },
  {
    id: "certificate-profiles",
    category: "certificates",
    title: "Как настроить профили сертификатов",
    summary:
      "В каком порядке связать центр сертификации, профиль сертификата и его потребителей.",
    intro:
      "Страница «Сертификаты» описывает желаемые параметры PKI. Сертификаты выпускаются и применяются отдельно, во время установки.",
    sections: [
      {
        title: "Порядок настройки",
        steps: [
          "Создайте управляемый центр сертификации.",
          "Создайте профиль сертификата и укажите центр, назначение ключа и правила SAN.",
          "При необходимости создайте профиль TLS и область применения: обе сущности ссылаются на профиль сертификата независимо друг от друга.",
          "Сохраните проект и проверьте сохранённую версию через Core.",
        ],
      },
      {
        title: "Пустые поля",
        text: "Пустые поля наследуют значения по умолчанию роли и не записываются в проект. DNS-имена и IP-адреса, которые нужно задать явно, указываются в настройках области применения.",
      },
    ],
    targetPage: "certificates",
  },
  {
    id: "certificate-identities",
    category: "certificates",
    title: "Откуда берутся имена и SAN",
    summary:
      "Почему итоговые DNS-имена и SAN показываются только после актуальной проверки Core.",
    intro:
      "Поля DNS/IP задают явные значения. Итоговые идентичности сертификатов Core рассчитывает с учётом конфигурации проекта и показывает по актуальным данным проверки.",
    sections: [
      {
        title: "Проверить результат",
        steps: [
          "Сохраните изменения проекта.",
          "Запустите проверку Core для сохранённой версии.",
          "На странице «Сертификаты» откройте блок «Проверка Core» и просмотрите рассчитанные имена и SAN.",
        ],
      },
      {
        title: "Если проект изменился",
        text: "Результат предыдущей проверки может относиться к старой версии. Сохраните актуальные изменения и повторите проверку; итоговое влияние виртуального IP также определяет Core.",
      },
    ],
    targetPage: "certificates",
  },
  {
    id: "certificate-store-password",
    category: "certificates",
    title: "Пароль Java-хранилищ PKCS#12",
    summary: "Как задаётся пароль keystore и truststore и где он хранится.",
    intro:
      "Пароль защищает Java-хранилища PKCS#12 (keystore/truststore). Его можно задать или заменить в верхнем блоке страницы «Сертификаты».",
    sections: [
      {
        title: "Задать пароль",
        steps: [
          "Сначала сохраните учётные данные выбранного узла выполнения.",
          "Введите новый пароль хранилищ и сохраните его в сеансе Installer.",
          "Перед установкой убедитесь, что пароль задан в текущем сеансе.",
        ],
      },
      {
        title: "Срок действия и восстановление",
        text: "Пароль не входит в файлы проекта и хранится только в активном сеансе Installer. Если пароль существующего хранилища неизвестен, Core пересоздаст его из текущих PEM-сертификатов и ключа при применении.",
      },
    ],
    warning:
      "Не записывайте пароль в проект, журналы или диагностику. Экран сертификатов не выпускает и не перевыпускает сертификаты.",
    targetPage: "certificates",
  },
  {
    id: "save-project",
    category: "project",
    title: "Создание, открытие и сохранение проекта",
    summary:
      "Как сохранить желаемую конфигурацию и проверить именно сохранённую версию.",
    intro:
      "Проект хранит желаемую конфигурацию: серверы, настройки сервисов и их размещение. Черновые изменения применяются не сразу — сначала просмотрите их и сохраните проект.",
    sections: [
      {
        title: "Порядок работы",
        steps: [
          "Откройте существующий проект или создайте новый.",
          "Внесите изменения на нужных страницах.",
          "Просмотрите изменения и нажмите «Сохранить проект».",
          "Запустите проверку Core для сохранённой версии.",
        ],
      },
    ],
    warning:
      "Проверка оценивает сохранённую версию проекта. Несохранённый черновик в неё не входит.",
    targetPage: "project",
  },
  {
    id: "bundle-catalog",
    category: "project",
    title: "Что такое набор установки",
    summary:
      "Почему каталог сервисов зависит от привязанного проверенного набора.",
    intro:
      "Набор установки содержит проверенное окружение Core и каталог возможностей сервисов. Проект закреплён за определённым набором и каталогом.",
    sections: [
      {
        title: "Если набор недоступен",
        text: "Настройки проекта сохраняются, но редактирование сервисов, проверка Core и создание плана могут быть недоступны. Используйте набор из доверенного источника и сравнивайте digest перед привязкой.",
        steps: [
          "Откройте страницу «Проект».",
          "Проверьте наличие и совместимость набора.",
          "Сравните версии и digest до подтверждения привязки.",
        ],
      },
    ],
    targetPage: "project",
  },
  {
    id: "add-server",
    category: "servers",
    title: "Добавление сервера",
    summary: "Как задать целевой узел и параметры подключения.",
    intro:
      "Добавьте сервер проекта, чтобы указать целевой узел, куда планируется установка.",
    sections: [
      {
        title: "Добавить сервер",
        steps: [
          "Откройте страницу «Серверы» и нажмите «Добавить сервер».",
          "Укажите имя узла, адрес и SSH-параметры.",
          "Выберите сохранённую ссылку на учётные данные или задайте их в предусмотренном интерфейсе.",
          "Сохраните изменение в черновик, затем сохраните проект целиком.",
        ],
      },
    ],
    warning:
      "Пароль и закрытый ключ не записываются в файлы проекта. Для нового узла проверьте SSH-ключ и сравните отпечаток с доверенным источником.",
    targetPage: "servers",
  },
  {
    id: "execution-node",
    category: "servers",
    title: "Подключение и подготовка узла выполнения",
    summary:
      "Чем Execution Node отличается от целевых серверов и как проверить его готовность.",
    intro:
      "Execution Node — узел, на котором запускаются Core, Python и Ansible. Это отдельная роль от серверов, на которые устанавливаются сервисы.",
    sections: [
      {
        title: "Проверить готовность",
        steps: [
          "Выберите нужный узел выполнения.",
          "Проверьте доступ по SSH и доверие к ключу узла.",
          "Запустите проверку готовности.",
          "Устраните показанную ошибку и повторите проверку.",
        ],
      },
    ],
    warning:
      "Подготовка узла не означает, что проект проверен или установка запущена. Не подтверждайте неизвестный SSH-отпечаток.",
    targetPage: "servers",
  },
  {
    id: "service-catalog",
    category: "services",
    title: "Каталог и настройки сервисов",
    summary: "Как добавить в проект возможность из каталога и настроить её.",
    intro:
      "Каталог показывает возможности, поддерживаемые текущим набором установки. Наличие сервиса в каталоге не означает, что он включён в проект.",
    sections: [
      {
        title: "Добавить сервис",
        steps: [
          "Создайте экземпляр сервиса в проекте.",
          "Задайте параметры экземпляра.",
          "Сохраните проект и выполните проверку Core.",
        ],
      },
    ],
    warning:
      "Несколько экземпляров одного типа могут иметь разные имена и настройки.",
    targetPage: "services",
  },
  {
    id: "placement",
    category: "services",
    title: "Размещение ролей на серверах",
    summary: "Как назначить серверы участникам сервисов.",
    intro:
      "Топология определяет, какие экземпляры сервисов и роли должны размещаться на серверах проекта.",
    sections: [
      {
        title: "Изменить размещение",
        steps: [
          "Откройте страницу «Топология».",
          "Выберите представление по сервисам или серверам.",
          "Назначьте участникам подходящие серверы и роли.",
          "Сохраните проект и проверьте результат через Core.",
        ],
      },
    ],
    warning:
      "Размещение — желаемая конфигурация. Итоговые зависимости вычисляет Core при проверке.",
    targetPage: "topology",
  },
  {
    id: "entry-points",
    category: "services",
    title: "Точки входа и адреса сервисов",
    summary: "Как связать сервисы-поставщики с компонентами-потребителями.",
    intro:
      "Точки входа связывают сервисы-поставщики с компонентами, которым нужны их адреса. Настраивайте назначения, поддерживаемые выбранным каталогом.",
    sections: [
      {
        title: "Если назначение не проходит проверку",
        text: "Итоговые адреса, имена и параметры доступа рассчитывает Core из конфигурации проекта. Исправьте несовместимое или отсутствующее назначение в проекте и повторите проверку.",
        steps: [
          "Откройте «Топология» и найдите нужное назначение.",
          "Проверьте выбранные сервис и потребителя.",
          "Сохраните проект и повторите проверку Core.",
        ],
      },
    ],
    warning:
      "Не подставляйте предполагаемые адреса вручную вместо результата Core.",
    targetPage: "topology",
  },
  {
    id: "verify-plan",
    category: "installation",
    title: "Проверка проекта и план установки",
    summary:
      "Почему проверка проекта не запускает установку и что требуется для выполнения.",
    intro:
      "Проверка Core анализирует сохранённый проект. Она не запускает Ansible на целевых серверах и не разрешает установку.",
    sections: [
      {
        title: "Подготовить выполнение",
        steps: [
          "Сохраните проект.",
          "Выполните проверку и устраните найденные ошибки.",
          "Создайте свежий план для текущей версии проекта и узла выполнения.",
          "Просмотрите действия и обязательные подтверждения, затем одобрите план.",
          "Запустите выполнение.",
        ],
      },
    ],
    warning:
      "Изменение проекта или узла выполнения может сделать проверку или план устаревшими. Повторите соответствующий шаг.",
    targetPage: "installation",
  },
  {
    id: "review-plan",
    category: "installation",
    title: "Просмотр и запуск плана",
    summary: "Что проверить перед одобрением плана и как оценивать результат.",
    intro:
      "План описывает конкретные действия для сохранённой версии проекта и выбранного узла выполнения.",
    sections: [
      {
        title: "Перед запуском",
        steps: [
          "Проверьте сервисы, серверы и действия в плане.",
          "Прочитайте обязательные подтверждения.",
          "Одобрите актуальный план.",
          "Запустите выполнение и дождитесь терминального результата.",
          "Учитывайте результат проверки сервисов отдельно от успешного применения изменений.",
        ],
      },
    ],
    warning:
      "Одобрение относится к конкретному плану. После изменения проекта создайте и проверьте новый план.",
    targetPage: "installation",
  },
  {
    id: "read-logs",
    category: "logs",
    title: "Как читать журнал выполнения",
    summary: "Как найти проблемный этап, узел и код ошибки.",
    intro:
      "Журнал показывает события выбранного запуска: этапы, действия, узлы, статусы и безопасные сообщения.",
    sections: [
      {
        title: "Найти нужное событие",
        steps: [
          "Откройте «Журналы».",
          "Выберите запуск по ID и времени.",
          "Просмотрите статус и сообщения событий.",
          "Если указана ошибка, найдите её код или описание в разделе «Ошибки».",
        ],
      },
    ],
    warning:
      "Сообщения могут быть сокращены или очищены от чувствительных данных. Проверяйте журналы перед передачей другим людям.",
    targetPage: "logs",
  },
  {
    id: "catalog-unavailable",
    category: "errors",
    title: "Почему каталог может быть недоступен?",
    summary: "Что проверить, если набор или каталог не соответствует проекту.",
    intro:
      "Проект закреплён за набором установки и каталогом сервисов. Если проверенный набор отсутствует или его каталог не соответствует проекту, настройки остаются на месте, но некоторые действия недоступны.",
    sections: [
      {
        title: "Что проверить",
        steps: [
          "Откройте страницу «Проект» и проверьте состояние привязки.",
          "Убедитесь, что нужный проверенный набор доступен.",
          "Сравните версию и digest перед привязкой.",
        ],
      },
    ],
    warning: "Не меняйте digest вручную.",
    targetPage: "project",
  },
  {
    id: "refresh-bundle",
    category: "errors",
    title: "Как обновить привязку существующего проекта?",
    summary:
      "Безопасная последовательность проверки и подтверждения нового набора.",
    intro:
      "Обнаружение нового набора само по себе не меняет привязку проекта. Сначала сравните его с текущей привязкой и убедитесь, что набор получен из доверенного источника.",
    sections: [
      {
        title: "Обновить привязку",
        steps: [
          "Создайте резервную копию через «Экспортировать проект».",
          "Поместите полученный набор целиком в папку bundle внутри проекта.",
          "На странице «Проект» нажмите «Проверить новый набор».",
          "Сравните текущий и новый digest, версии набора и каталога.",
          "Если значения ожидаемые, нажмите «Привязать».",
          "Откройте проект заново, проверьте его через Core и создайте свежий план перед установкой.",
        ],
      },
    ],
    warning:
      "Не редактируйте digest вручную в project.yml и не выбирайте набор только по признаку «последний».",
    targetPage: "project",
  },
  {
    id: "bundle-rebind-after-interrupted-run",
    category: "errors",
    title: "Кнопка «Проверить новый набор» не срабатывает после прерывания",
    summary:
      "Как проверить прежний запуск и безопасно повторить обнаружение набора.",
    intro:
      "Перепривязка набора блокируется, пока предыдущий запуск не подтверждён как завершённый. Поэтому вместо проверки может появиться общее сообщение: «Не удалось открыть проект в режиме только для чтения. Проект на диске не изменён.»",
    sections: [
      {
        title: "Проверить прежний запуск",
        steps: [
          "После перезапуска приложения при необходимости заново задайте SSH-учётные данные и подтвердите доверие к отпечатку узла.",
          "Откройте «Серверы» и в блоке узла выполнения нажмите «Проверить прежний запуск», чтобы получить его фактический статус.",
          "Если запуск ещё активен, сверьте его ID и нажмите «Подключиться», чтобы восстановить наблюдение. Дождитесь завершения; подключение не запускает установку повторно.",
          "Когда запуск подтверждён как завершённый, проверьте, что полный проверенный набор находится в папке bundle внутри проекта, и снова нажмите «Проверить новый набор» на странице «Проект».",
        ],
      },
    ],
    warning:
      "Не удаляйте записи или журналы запуска и не редактируйте блокировки проекта вручную.",
    targetPage: "servers",
  },
  {
    id: "execution-not-updating",
    category: "errors",
    title: "Если страница «Выполнение» перестала обновляться",
    summary: "Потеря связи не доказывает, что запущенный процесс остановился.",
    intro:
      "Потеря связи с Execution Node не означает, что выполнение завершилось. Сначала проверьте состояние исходного запуска.",
    sections: [
      {
        title: "Проверить состояние",
        steps: [
          "Запишите ID выполнения со страницы установки или из журнала.",
          "Откройте исходный проект. На странице «Серверы» выберите тот же узел выполнения, на котором запускалась установка.",
          "Если SSH-сессия истекла или приложение перезапускалось, заново задайте учётные данные исходного технического пользователя. Проверьте сервер и подтвердите доверие после независимой сверки отпечатка SSH-ключа.",
          "В блоке узла выполнения нажмите «Проверить прежний запуск». Сверьте показанные ID запуска, ревизию проекта и фактическое состояние.",
          "Если запуск найден и доступна кнопка «Подключиться», нажмите её. Приложение откроет «Установка → Выполнение» и восстановит наблюдение за тем же запуском и его событиями. Новый план, утверждение и повторный Start не требуются.",
          "Сверьте последние события и их время, затем дождитесь терминального результата. Если запуск уже завершён, используйте его фактический результат; повторно запускать установку для восстановления наблюдения не нужно.",
          "Если запуск недоступен или его состояние не подтверждено, проверьте SSH-доступ и исходный узел выполнения, затем повторите проверку прежнего запуска.",
        ],
      },
    ],
    warning:
      "Не запускайте операцию повторно, не удаляйте данные запуска и не считайте результат успешным или ошибочным только по замершему экрану.",
    targetPage: "servers",
  },
  {
    id: "blocked-plan",
    category: "errors",
    title: "Если проверка или план заблокированы",
    summary: "Как действовать по finding и повторно проверить конфигурацию.",
    intro:
      "Найдите сообщение Core или finding, который блокирует действие. В нём указаны причина и область конфигурации, требующая внимания.",
    sections: [
      {
        title: "Устранить блокировку",
        steps: [
          "Запишите код и текст ошибки.",
          "Перейдите к указанному серверу, сервису или настройке.",
          "Исправьте желаемую конфигурацию и сохраните проект.",
          "Повторите проверку Core.",
          "После успешной проверки создайте свежий план.",
        ],
      },
    ],
    warning:
      "Не обходите блокировку ручным запуском ролей и не используйте старый план после изменения проекта.",
    targetPage: "installation",
  },
];

const LOGS_PAGE_SIZE = 512;
const LOGS_VISIBLE_COLUMNS_KEY = "platform-installer.logs.visible-columns";

type EventColumn = {
  key: string;
  label: string;
  value: (event: InstallationEventView) => string;
};

const eventColumns: EventColumn[] = [
  { key: "sequence", label: "№", value: (event) => String(event.sequence) },
  {
    key: "timestamp",
    label: "Время",
    value: (event) => eventTimestampLabel(event.timestamp),
  },
  {
    key: "eventType",
    label: "Тип события",
    value: (event) => eventTypeLabel(event.eventType),
  },
  {
    key: "status",
    label: "Статус",
    value: (event) => eventStatusLabel(event.status),
  },
  {
    key: "safeMessage",
    label: "Сообщение",
    value: (event) => event.safeMessage,
  },
  { key: "phaseId", label: "Этап", value: (event) => event.phaseId || "—" },
  {
    key: "actionId",
    label: "Действие",
    value: (event) => event.actionId || "—",
  },
  {
    key: "serviceDeployment",
    label: "Развёртывание сервиса",
    value: (event) => event.serviceDeployment || "—",
  },
  { key: "host", label: "Узел", value: (event) => event.host || "—" },
  {
    key: "taskRole",
    label: "Роль задачи",
    value: (event) => event.task?.role || "—",
  },
  {
    key: "taskName",
    label: "Задача",
    value: (event) =>
      taskNameWithoutRole(event) || (event.task ? "Скрыто" : "—"),
  },
  {
    key: "taskUUID",
    label: "ID задачи",
    value: (event) => event.task?.uuid || "—",
  },
  {
    key: "elapsed",
    label: "Длительность",
    value: (event) =>
      event.elapsedMilliseconds === undefined
        ? "—"
        : `${event.elapsedMilliseconds} мс`,
  },
  {
    key: "errorCode",
    label: "Код ошибки",
    value: (event) => event.errorCode || "—",
  },
  {
    key: "errorSummary",
    label: "Описание ошибки",
    value: (event) => event.errorSummary || "—",
  },
  {
    key: "redacted",
    label: "Редакция данных",
    value: (event) => (event.redacted ? "Применена" : "Нет"),
  },
  { key: "runId", label: "ID запуска", value: (event) => event.runId },
];

const defaultVisibleColumns = [
  "timestamp",
  "eventType",
  "safeMessage",
  "serviceDeployment",
  "host",
  "status",
];

function initialVisibleColumns(): string[] {
  try {
    const saved = window.sessionStorage.getItem(LOGS_VISIBLE_COLUMNS_KEY);
    if (saved !== null) {
      const parsed: unknown = JSON.parse(saved);
      if (Array.isArray(parsed)) {
        const selected = new Set(
          parsed.filter((key): key is string => typeof key === "string"),
        );
        return eventColumns
          .filter((column) => selected.has(column.key))
          .map((column) => column.key);
      }
    }
  } catch {
    // Storage may be unavailable in restricted WebView contexts.
  }
  return defaultVisibleColumns;
}

function eventTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    RUN_STARTED: "Запуск начат",
    PHASE_STARTED: "Этап начат",
    ACTION_STARTED: "Действие начато",
    TASK_STARTED: "Задача начата",
    TASK_COMPLETED: "Задача завершена",
    ACTION_COMPLETED: "Действие завершено",
    PHASE_COMPLETED: "Этап завершён",
    RUN_COMPLETED: "Запуск завершён",
    DIAGNOSTIC: "Диагностика",
  };
  return labels[value] || value;
}

function eventStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    PENDING: "Ожидает",
    RUNNING: "Выполняется",
    SUCCESS: "Успешно",
    CHANGED: "Изменено",
    SKIPPED: "Пропущено",
    FAILED: "Ошибка",
    CANCELLED: "Отменено",
    INTERRUPTED: "Прервано",
  };
  return labels[value] || value;
}

function EventLog({
  events,
  runId,
}: {
  events: InstallationEventView[];
  runId?: string;
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [selectedSequence, setSelectedSequence] = useState<number>();
  const [visibleColumns, setVisibleColumns] = useState<string[]>(
    initialVisibleColumns,
  );
  useEffect(() => {
    try {
      window.sessionStorage.setItem(
        LOGS_VISIBLE_COLUMNS_KEY,
        JSON.stringify(visibleColumns),
      );
    } catch {
      // Keep the selection in component state if storage is unavailable.
    }
  }, [visibleColumns]);
  useEffect(() => {
    setPage(0);
    setSelectedSequence(undefined);
  }, [runId]);
  const orderedEvents = useMemo(
    () => [...events].sort((a, b) => b.sequence - a.sequence),
    [events],
  );
  const filteredEvents = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("ru");
    if (!needle) return orderedEvents;
    return orderedEvents.filter((event) =>
      eventColumns.some((column) =>
        column.value(event).toLocaleLowerCase("ru").includes(needle),
      ),
    );
  }, [orderedEvents, query]);
  const pageCount = Math.max(
    1,
    Math.ceil(filteredEvents.length / LOGS_PAGE_SIZE),
  );
  const currentPage = Math.min(page, pageCount - 1);
  const pageEvents = filteredEvents.slice(
    currentPage * LOGS_PAGE_SIZE,
    (currentPage + 1) * LOGS_PAGE_SIZE,
  );
  const selectedEvent =
    filteredEvents.find((event) => event.sequence === selectedSequence) ||
    filteredEvents[0];
  const visible = eventColumns.filter((column) =>
    visibleColumns.includes(column.key),
  );

  return (
    <>
      <div className="event-log-toolbar">
        <label className="event-log-search">
          Поиск по событиям
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(0);
            }}
            placeholder="Сообщение, задача, узел…"
          />
        </label>
        <details className="event-log-columns">
          <summary>
            Колонки ({visible.length} из {eventColumns.length})
          </summary>
          <fieldset>
            <legend>Показывать колонки</legend>
            {eventColumns.map((column) => (
              <label key={column.key}>
                <input
                  type="checkbox"
                  checked={visibleColumns.includes(column.key)}
                  onChange={(event) =>
                    setVisibleColumns((current) =>
                      event.target.checked
                        ? [...current, column.key]
                        : current.filter((key) => key !== column.key),
                    )
                  }
                />
                {column.label}
              </label>
            ))}
          </fieldset>
        </details>
      </div>
      <div className="event-log-layout">
        <section
          className="event-log-table-panel"
          aria-label="События текущего запуска"
        >
          <div className="event-log-table-scroll">
            <table className="event-log-table">
              <thead>
                <tr>
                  {visible.map((column) => (
                    <th key={column.key} scope="col">
                      {column.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageEvents.map((event) => (
                  <tr
                    key={`${event.runId}-${event.sequence}`}
                    className={
                      selectedEvent?.sequence === event.sequence
                        ? "is-selected"
                        : ""
                    }
                    onClick={() => setSelectedSequence(event.sequence)}
                  >
                    {visible.map((column) => (
                      <td key={column.key} title={column.value(event)}>
                        {column.value(event)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {pageEvents.length === 0 && (
              <p className="event-log-empty">
                {events.length
                  ? "По заданным условиям события не найдены."
                  : "События появятся здесь после запуска плана."}
              </p>
            )}
          </div>
          <footer className="event-log-pagination">
            <span>
              {filteredEvents.length
                ? `Показаны ${currentPage * LOGS_PAGE_SIZE + 1}–${Math.min((currentPage + 1) * LOGS_PAGE_SIZE, filteredEvents.length)} из ${filteredEvents.length}`
                : "Нет событий"}
            </span>
            <button
              type="button"
              onClick={() => setPage((value) => Math.max(0, value - 1))}
              disabled={currentPage === 0}
            >
              Назад
            </button>
            <span>
              Страница {currentPage + 1} из {pageCount}
            </span>
            <button
              type="button"
              onClick={() =>
                setPage((value) => Math.min(pageCount - 1, value + 1))
              }
              disabled={currentPage >= pageCount - 1}
            >
              Далее
            </button>
          </footer>
        </section>
        <aside className="event-log-details" aria-label="Подробности события">
          <h2>Детали события</h2>
          {selectedEvent ? (
            <>
              <strong>
                {eventTypeLabel(selectedEvent.eventType)} ·{" "}
                {eventStatusLabel(selectedEvent.status)}
              </strong>
              <p>{selectedEvent.safeMessage}</p>
              <dl>
                <dt>Время</dt>
                <dd>{eventTimestampLabel(selectedEvent.timestamp)}</dd>
                <dt>Этап / действие</dt>
                <dd>
                  {[selectedEvent.phaseId, selectedEvent.actionId]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </dd>
                <dt>Развёртывание сервиса</dt>
                <dd>{selectedEvent.serviceDeployment || "—"}</dd>
                <dt>Узел</dt>
                <dd>{selectedEvent.host || "—"}</dd>
                <dt>Роль задачи</dt>
                <dd>{selectedEvent.task?.role || "—"}</dd>
                <dt>Задача</dt>
                <dd>
                  {taskNameWithoutRole(selectedEvent) ||
                    (selectedEvent.task ? "Скрыто" : "—")}
                </dd>
                <dt>ID задачи</dt>
                <dd>{selectedEvent.task?.uuid || "—"}</dd>
                <dt>Длительность</dt>
                <dd>
                  {selectedEvent.elapsedMilliseconds === undefined
                    ? "—"
                    : `${selectedEvent.elapsedMilliseconds} мс`}
                </dd>
                <dt>Ошибка</dt>
                <dd>
                  {[selectedEvent.errorCode, selectedEvent.errorSummary]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </dd>
                <dt>Редакция данных</dt>
                <dd>{selectedEvent.redacted ? "Применена" : "Нет"}</dd>
                <dt>ID запуска</dt>
                <dd>{selectedEvent.runId || runId || "—"}</dd>
              </dl>
            </>
          ) : (
            <p>Выберите событие, чтобы увидеть подробности.</p>
          )}
        </aside>
      </div>
    </>
  );
}

type Props = {
  page: string;
  managed?: ManagedProjectView;
  projectSettingDraftValues?: Partial<
    Record<"platform_data_root_directory" | "platform_name_prefix", string>
  >;
  onAppendProjectSetting?: (intent: {
    operation: "SetProjectSetting";
    setting: "platform_data_root_directory" | "platform_name_prefix";
    value: string;
  }) => Promise<boolean>;
  editError?: EditResult["error"] | null;
  events: InstallationEventView[];
  runId?: string;
  configVersion?: number;
  serverTypes: Array<{ id: string; displayName: string }>;
  configError: string | null;
  onNavigate?: (page: HelpPageId) => void;
};

function HelpPage({ onNavigate }: { onNavigate?: (page: HelpPageId) => void }) {
  const [query, setQuery] = useState("");
  const [categoryId, setCategoryId] = useState<string>();
  const [articleId, setArticleId] = useState<string>();
  const normalizedQuery = query.trim().toLocaleLowerCase("ru");
  const matches = useMemo(() => {
    const candidates = helpArticles.filter(
      (article) =>
        !categoryId || normalizedQuery || article.category === categoryId,
    );
    if (!normalizedQuery) return candidates;
    return candidates.filter((article) => {
      const category = helpCategories.find(
        (item) => item.id === article.category,
      );
      const searchable = [
        category?.title,
        article.title,
        article.summary,
        article.intro,
        article.warning,
        ...article.sections.flatMap((section) => [
          section.title,
          section.text,
          ...(section.steps || []),
        ]),
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("ru");
      return searchable.includes(normalizedQuery);
    });
  }, [categoryId, normalizedQuery]);
  const selectedArticle = matches.find((article) => article.id === articleId);
  const selectedCategory = helpCategories.find(
    (item) => item.id === categoryId,
  );

  const openCategory = (id: string) => {
    const firstArticle = helpArticles.find(
      (article) => article.category === id,
    );
    setQuery("");
    setCategoryId(id);
    setArticleId(firstArticle?.id);
  };
  const openArticle = (article: (typeof helpArticles)[number]) => {
    setCategoryId(article.category);
    setArticleId(article.id);
  };

  return (
    <section className="utility-page help-page" aria-labelledby="help-title">
      <header className="utility-page-title">
        <div>
          <h1 id="help-title">Справка</h1>
          <p>Инструкции по проекту, настройке и устранению ошибок.</p>
        </div>
      </header>
      <label className="help-search">
        <span className="visually-hidden">Поиск по справке</span>
        <input
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setArticleId(undefined);
          }}
          placeholder="Например: каталог недоступен"
        />
      </label>

      {selectedArticle ? (
        <div className="help-reading-layout">
          <aside className="help-article-list" aria-label="Статьи раздела">
            <div className="help-list-heading">
              <button
                type="button"
                className="help-back-link"
                onClick={() => {
                  setArticleId(undefined);
                  setCategoryId(undefined);
                }}
              >
                Все разделы
              </button>
              <h2>
                {normalizedQuery
                  ? "Результаты поиска"
                  : selectedCategory?.title}
              </h2>
            </div>
            {matches.map((article) => (
              <button
                type="button"
                key={article.id}
                className={`help-article-link${article.id === selectedArticle.id ? " is-selected" : ""}`}
                onClick={() => openArticle(article)}
              >
                {article.title}
              </button>
            ))}
          </aside>
          <article
            className="utility-card help-article"
            aria-labelledby="help-article-title"
          >
            <div className="help-breadcrumb">
              <button
                type="button"
                className="help-back-link"
                onClick={() => {
                  setArticleId(undefined);
                  setCategoryId(undefined);
                }}
              >
                Справка
              </button>
              <span aria-hidden="true">›</span>
              <button
                type="button"
                className="help-back-link"
                onClick={() => setArticleId(undefined)}
              >
                {selectedCategory?.title}
              </button>
            </div>
            <h2 id="help-article-title">{selectedArticle.title}</h2>
            <p className="help-article-intro">{selectedArticle.intro}</p>
            {selectedArticle.sections.map((section) => (
              <section className="help-article-section" key={section.title}>
                <h3>{section.title}</h3>
                {section.text && <p>{section.text}</p>}
                {section.steps && (
                  <ol>
                    {section.steps.map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ol>
                )}
              </section>
            ))}
            {selectedArticle.warning && (
              <p className="help-warning" role="note">
                {selectedArticle.warning}
              </p>
            )}
            {selectedArticle.targetPage && onNavigate && (
              <button
                type="button"
                className="help-open-page"
                onClick={() => onNavigate(selectedArticle.targetPage!)}
              >
                Открыть страницу «{helpPageLabels[selectedArticle.targetPage]}»
              </button>
            )}
          </article>
        </div>
      ) : normalizedQuery ? (
        <section
          className="help-search-results"
          aria-live="polite"
          aria-label="Результаты поиска"
        >
          <h2>Результаты поиска</h2>
          {matches.length ? (
            matches.map((article) => {
              const category = helpCategories.find(
                (item) => item.id === article.category,
              );
              return (
                <button
                  type="button"
                  className="help-search-result"
                  key={article.id}
                  onClick={() => openArticle(article)}
                >
                  <span>{category?.title}</span>
                  <strong>{article.title}</strong>
                  <small>{article.summary}</small>
                </button>
              );
            })
          ) : (
            <p role="status">По этому запросу статьи не найдены.</p>
          )}
        </section>
      ) : categoryId && selectedCategory ? (
        <section
          className="help-search-results"
          aria-labelledby="help-category-title"
        >
          <button
            type="button"
            className="help-back-link"
            onClick={() => setCategoryId(undefined)}
          >
            Все разделы
          </button>
          <h2 id="help-category-title">{selectedCategory.title}</h2>
          {matches.map((article) => (
            <button
              type="button"
              className="help-search-result"
              key={article.id}
              onClick={() => openArticle(article)}
            >
              <strong>{article.title}</strong>
              <small>{article.summary}</small>
            </button>
          ))}
        </section>
      ) : (
        <section
          className="help-category-grid"
          aria-labelledby="help-categories-title"
        >
          <h2 id="help-categories-title">Темы</h2>
          <div className="help-category-cards">
            {helpCategories.map((category) => (
              <button
                type="button"
                className="help-category-card"
                key={category.id}
                onClick={() => openCategory(category.id)}
              >
                <span className="help-category-card-heading">
                  <strong>{category.title}</strong>
                  <span aria-hidden="true">›</span>
                </span>
                <span className="help-category-description">
                  {category.description}
                </span>
                <small>
                  Статей:{" "}
                  {
                    helpArticles.filter(
                      (article) => article.category === category.id,
                    ).length
                  }
                </small>
              </button>
            ))}
          </div>
        </section>
      )}
    </section>
  );
}

export function UtilityPages({
  page,
  managed,
  projectSettingDraftValues,
  onAppendProjectSetting,
  editError,
  events,
  runId,
  configVersion,
  serverTypes,
  configError,
  onNavigate,
}: Props) {
  const savedDataRootDirectory = managed?.dataRootDirectory || "/var/lib";
  const savedNamePrefix = managed?.namePrefix || "";
  const draftDataRootDirectory =
    projectSettingDraftValues?.platform_data_root_directory;
  const draftNamePrefix = projectSettingDraftValues?.platform_name_prefix;
  const dataRootDirectoryChanged =
    draftDataRootDirectory !== undefined &&
    draftDataRootDirectory !== savedDataRootDirectory;
  const namePrefixChanged =
    draftNamePrefix !== undefined && draftNamePrefix !== savedNamePrefix;
  const [dataRootDirectory, setDataRootDirectory] = useState(
    draftDataRootDirectory || savedDataRootDirectory,
  );
  const [namePrefix, setNamePrefix] = useState(
    draftNamePrefix ?? savedNamePrefix,
  );
  const [settingBusy, setSettingBusy] = useState(false);
  useEffect(() => {
    setDataRootDirectory(draftDataRootDirectory || savedDataRootDirectory);
    setNamePrefix(draftNamePrefix ?? savedNamePrefix);
  }, [
    managed?.projectRevision,
    savedDataRootDirectory,
    savedNamePrefix,
    draftDataRootDirectory,
    draftNamePrefix,
  ]);
  const stageSetting = async (
    setting: "platform_data_root_directory" | "platform_name_prefix",
    value: string,
  ) => {
    if (!onAppendProjectSetting || !managed) return;
    setSettingBusy(true);
    try {
      await onAppendProjectSetting({
        operation: "SetProjectSetting",
        setting,
        value,
      });
    } finally {
      setSettingBusy(false);
    }
  };
  if (page === "help") return <HelpPage onNavigate={onNavigate} />;

  if (page === "logs")
    return (
      <section className="utility-page" aria-labelledby="logs-title">
        <header className="utility-page-title">
          <div>
            <h1 id="logs-title">Журналы</h1>
            <p>События текущего выполнения в безопасном представлении.</p>
          </div>
          {runId && <span className="utility-status">Выполнение {runId}</span>}
        </header>
        <EventLog events={events} runId={runId} />
      </section>
    );

  if (page === "about")
    if (page === "about")
      return (
        <section className="utility-page" aria-labelledby="about-title">
          <header className="utility-page-title">
            <div>
              <h1 id="about-title">О программе</h1>
              <p>Platform Installer V2</p>
            </div>
          </header>
          <section className="utility-card">
            <h2>Сведения о программе</h2>
            <dl className="about-details">
              <dt>Продукт</dt>
              <dd>Platform Installer V2</dd>
              <dt>Интерфейс</dt>
              <dd>Wails · React</dd>
              <dt>Схема конфигурации приложения</dt>
              <dd>
                {configVersion === undefined
                  ? "Недоступна"
                  : `v${configVersion}`}
              </dd>
              <dt>Типы серверов</dt>
              <dd>
                {serverTypes.length
                  ? serverTypes.map((item) => item.displayName).join(", ")
                  : "Недоступны"}
              </dd>
            </dl>
            {configError && <p role="status">{configError}</p>}
          </section>
        </section>
      );

  if (page === "settings")
    return (
      <section className="utility-page" aria-labelledby="settings-title">
        <header className="utility-page-title">
          <div>
            <h1 id="settings-title">Настройки</h1>
            <p>Параметры проекта и локальная конфигурация приложения.</p>
          </div>
        </header>
        <section className="utility-card">
          <h2>Параметры проекта</h2>
          <p>
            Изменения добавляются в общий черновик проекта. Просмотрите их и
            нажмите «Сохранить» в шапке.
          </p>
          {editError && (
            <p className="field-error" role="alert">
              <code>{editError.code}</code> — {editError.message}
            </p>
          )}
          <div
            className={`project-setting-field${dataRootDirectoryChanged ? " project-setting-field--changed" : ""}`}
          >
            <label>
              Корневой каталог данных сервисов
              <input
                value={dataRootDirectory}
                onChange={(event) => setDataRootDirectory(event.target.value)}
                disabled={!managed || settingBusy}
              />
            </label>
            {dataRootDirectoryChanged && (
              <small className="project-setting-draft-status" role="status">
                В черновике: <code>{draftDataRootDirectory}</code>. Сохраните
                проект в шапке, чтобы зафиксировать это значение.
              </small>
            )}
            <button
              type="button"
              disabled={
                !managed ||
                settingBusy ||
                dataRootDirectory ===
                  (draftDataRootDirectory ?? savedDataRootDirectory)
              }
              onClick={() =>
                void stageSetting(
                  "platform_data_root_directory",
                  dataRootDirectory,
                )
              }
            >
              Добавить каталог в черновик
            </button>
          </div>
          <p>
            Путь применяется к каталогам данных сервисов по умолчанию. Данные
            при изменении пути автоматически не переносятся.
          </p>
          <div
            className={`project-setting-field${namePrefixChanged ? " project-setting-field--changed" : ""}`}
          >
            <label>
              Префикс имён ресурсов
              <input
                value={namePrefix}
                onChange={(event) => setNamePrefix(event.target.value)}
                disabled={!managed || settingBusy}
              />
            </label>
            {namePrefixChanged && (
              <small className="project-setting-draft-status" role="status">
                В черновике задан префикс «{draftNamePrefix || "не задан"}».
                Сохраните проект в шапке, чтобы зафиксировать это значение.
              </small>
            )}
            <button
              type="button"
              disabled={
                !managed ||
                settingBusy ||
                namePrefix === (draftNamePrefix ?? savedNamePrefix)
              }
              onClick={() =>
                void stageSetting("platform_name_prefix", namePrefix)
              }
            >
              Добавить префикс в черновик
            </button>
          </div>
          <p>
            Пустое значение создаёт имена ресурсов сервисов без префикса. Новый
            префикс создаёт новые имена ресурсов; прежние ресурсы автоматически
            не переименовываются.
          </p>
        </section>
        <section className="utility-card">
          <h2>Конфигурация приложения</h2>
          {configError ? (
            <p role="status">{configError}</p>
          ) : (
            <>
              <p>
                Версия схемы:{" "}
                {configVersion === undefined
                  ? "загрузка…"
                  : `v${configVersion}`}
              </p>
              <p>
                Типы серверов:{" "}
                {serverTypes.length
                  ? serverTypes.map((item) => item.displayName).join(", ")
                  : "не заданы"}
              </p>
            </>
          )}
          <p>
            Учётные данные сеанса и секреты не сохраняются в настройках
            приложения.
          </p>
        </section>
      </section>
    );

  return null;
}
