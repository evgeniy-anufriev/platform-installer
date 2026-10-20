do
    local start_time_request = ngx.now() -- Фиксируем начало выполнения обработки запроса
    -- Подгружаем библиотеки
    local jwt = require "resty.jwt"
    local cjson = require "cjson"
    local http = require "resty.http"
    local openidc = require("resty.openidc")

    -- Функция проверки строки на то, что она не пустая
    local function isNotEmptyString(str)
        return str ~= nil and str ~= ""
    end

    -- Функция для получения атрибута canary или visibility_zone из токена
    local function get_attr_from_jwt(token, attr)
        -- извлекаем payload
        local _, payload = token:match("^([^.]+)%.([^.]+)%.?([^.]*)$")
        -- Подмена символов для корректной работы ngx.decode_base64
        payload = payload:gsub('-', '+'):gsub('_', '/')
        local pad = #payload % 4
        -- Восстанавливаем кооректный формат для работы с base64
        if pad ~= 0 then
            payload = payload .. string.rep('=', 4 - pad)
        end
        -- Декодируем
        local decoded = ngx.decode_base64(payload)

        local obj, err = cjson.decode(decoded)
        if attr == "canary" then
            return obj and obj.canary or ""
        end
        if attr == "visibility_zone" then
            return obj and obj.visibility_zone or ""
        end
        return ""
    end

    -- Функция обработки ответа по статусу. Принимает и возвращает оставшееся количество повторов запроса. Выполняет лог и паузу на 1 секунду, если остались повторные запросы
    local function handle_retrying_by_response_status(response_status, count, log_message)
        if count > 1 and ((response_status >= 500 and response_status ~= 520) or response_status == 400) then --TODO: почему в проверке был 400? как повторный запрос должен исправить 400?
            ngx.log(ngx.WARN, log_message)
            ngx.sleep(1)
            return count - 1
        end
        return -1
    end

    -- Функция разделенния переменных из data.env перечисленные через разделитель: ";"
    local function split(str)
          local res = {}
          for part in string.gmatch(str, "[^;]+") do
              table.insert(res,part)
          end
          return res
    end

    -- Блок кода по выводу окна ошибки (Начало)
    -- Функция подмены спец символов для защиты от инъекций
    local function escape_html(s)
        if not s then return "" end
        s = tostring(s)
        s = s:gsub("&", "&amp;")
             :gsub("<", "&lt;")
             :gsub(">", "&gt;")
             :gsub('"', "&quot;")
             :gsub("'", "&#39;")
        return s
    end

    -- Функция экранирования для JS-строки
    local function js_string_escape(s)
        if not s then return "" end
            s = s:gsub("\\", "\\\\")
            s = s:gsub("'", "\'")
            s = s:gsub('"', '\"')
            s = s:gsub("\n", "\n")
            s = s:gsub("\r", "\r")
            s = s:gsub("\t", "\t")
        return s
    end

    -- Генерация number used once для  разрешений script/style
    local function make_nonce()
        local n = tostring(ngx.now()) .. tostring(math.random())
        local b = ngx.encode_base64(n):gsub("=+$", "")
        return b
    end

    -- Функция для загрузки переменных окружения из файла
    local function getEnv(fileEnvPath)
        local env = {}
        for line in io.lines(fileEnvPath) do
            -- По шаблону: ключ все символы до знака равенства, значение все символы обернутые в двойные ковычки после знака равенста
            for key, value in string.gmatch(line, '([^=]+)="(.-)"') do
                env[key] = value
            end
        end
        return env
    end

    -- Функция форматирует строку именоваными параметрами. Параметры указываются в строке в виде ${PARAM_NAME}.
    -- s - строка для форматирования. Например, "текст, ${param1} and ${param2} и ещё текст";
    -- tab - таблица параметров и их значений. Например {param1 = "DERP", param2 = "DUMB"}
    local function interp(s, tab)
        return (s:gsub('($%b{})', function(w) return tab[w:sub(3, -2)] or w end))
    end

    local function errorWindow(url_logout, message, use_update_button, update_url, clear_cookies, http_status)
        -- Экранируем входные данные
        local esc_message = escape_html(message)
        local esc_logout = url_logout and escape_html(url_logout) or nil
        local esc_update_url = update_url and escape_html(update_url) or nil

        -- Удаляем куки
        if nil ~= clear_cookies and true == clear_cookies then
            local newcookies = {}
            table.insert(newcookies, "session=deleted; Expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; HttpOnly; Secure")
            table.insert(newcookies, "session_2=deleted; Expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; HttpOnly; Secure")
            table.insert(newcookies, "session_3=deleted; Expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; HttpOnly; Secure")
            table.insert(newcookies, "JSESSIONID=deleted; Expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; HttpOnly; Secure")
            ngx.header["Set-Cookie"] = newcookies
        end

        -- Генерируем nonce и ставим CSP. Указываем необходимые заголовки.
        local nonce = make_nonce()
        local csp = table.concat({
            "default-src 'none';", -- По умолчанию запрещаем загрузку всего
            "script-src 'self' 'nonce-" .. nonce .. "';", -- разрешаем только script с nonce (при добавлении скриптов необходимо будет спользовать nonce)
            "style-src 'self' 'nonce-" .. nonce .. "';", -- разрешаем только style с nonce
            "img-src 'self' data:;", --Разрешаем изображения с того же источника и data: URI (встроенные изображения)
            "connect-src 'self';", -- Разрешаем XHR/fetch/websocket только к тому же origin
            "font-src 'self';", -- Разрешаем подгружать шрифты только с того же origin
            "frame-ancestors 'none';", -- Запрещаем встраивание страницы в iframe/frames
            "base-uri 'none';", -- Запрещаем использование тега <base>, чтобы нельзя было менять базовый URL для ссылок/ресурсов
            "form-action 'self';", -- Разрешаем отправку форм только на тот же origin
            "object-src 'none';" --Запрещает загрузку и использование плагин‑типа ресурсов через теги <object>, <embed> и <applet> из любых источников.
        }, " ")

        ngx.header["Content-Security-Policy"] = csp -- Устанавливаем заголовок Content-Security-Policy в ответ
        ngx.header["X-Content-Type-Options"] = "nosniff" -- Запрещаем браузеру пытаться угадывать MIME‑тип (защищает от некоторых атак / XSS через неправильный Content-Type)
        ngx.header["X-Frame-Options"] = "DENY" -- Дополнительная защита от встраивания в iframe (можно опустить, если уже используете frame-ancestors в CSP)
        ngx.header["Referrer-Policy"] = "no-referrer-when-downgrade" -- Не посылать Referer при работе по HTTP
        ngx.header["Content-Type"] = "text/html; charset=utf-8"

        local button_fragment
        if use_update_button == true and esc_update_url then
            button_fragment = '<a href="' .. esc_update_url .. '" class="button">Обновить</a>'
        elseif esc_logout ~= nil then
            ngx.status = ngx.HTTP_UNAUTHORIZED
            button_fragment = '<a href="' .. esc_logout .. '" class="button">Выход</a>'
        else
            esc_update_url = escape_html(getEnv('/etc/nginx/data.env')["COMMON_REDIRECT_URL"])
            button_fragment = '<a href="' .. esc_logout .. '" class="button">Обновить</a>'
            ngx.status = ngx.HTTP_SERVICE_UNAVAILABLE
        end
        -- Переписываем статус переданным значением
        if isNotEmptyString(http_status) then
            ngx.status = http_status
        end

        -- Собираем HTML
        --справка о параметризации строки тут: http://lua-users.org/wiki/StringInterpolation
        local html_template = [[
            <!DOCTYPE html>
            <html lang="ru">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Доступ отсутствует</title>
                    <style nonce="${p_nonce}">
                        body, html {
                            align-items:center;
                            display:flex;
                            font-family:Arial, sans-serif;
                            height:100%;
                            justify-content:center;
                            margin:0;
                            text-align:center;
                        }
                        .header {
                            align-items:center;
                            background-color:#f1f1f1;
                            box-shadow:0 2px 4px rgba(0,0,0,0.1);
                            display:flex;
                            justify-content:space-between;
                            left:0;
                            padding:10px 20px;
                            position:fixed;
                            top:0;
                            width:100%;
                        }
                        .button {
                            background-color:green;
                            border:none;
                            border-radius:10px;
                            color:white;
                            cursor:pointer;
                            font-size:16px;
                            margin-right:40px;
                            padding:10px 20px;
                            text-decoration:none;
                        }
                        .page-title {
                            font-size:21px;
                        }
                        .container {
                            align-items:center;
                            display:flex;
                            flex-direction:column;
                            height:100%;
                            justify-content:center;
                            position:relative;
                            text-align:center;
                            top:-100px;
                            width:100%;
                        }
                        .greeting {
                            font-size:30px;
                            margin:10px 0;
                        }
                    </style>
                </head>
                <body>
                    <div class="header">
                        <div class="page-title">Сервис идентификации и управления доступом</div>
                        ${p_button_fragment}
                    </div>
                    <div class="container">
                        <div class="greeting">${p_message} &lt;${p_status}&gt;</div>
                        <div class="greeting">В случае некорректной работы сервиса обратитесь к администратору</div>
                    </div>
                </body>
            </html>
            ]]
        local completed_html = interp(html_template, {p_nonce = nonce, p_button_fragment = button_fragment, p_message = esc_message, p_status = ngx.status})
        ngx.say(completed_html)
        ngx.exit(ngx.status)
    end

    -- Инвалидация сессии нЖинкса по хартбиту
    local function invalidate_session_from_grant_access(frontend_url, message_to_user, clear_cookies)
        errorWindow(frontend_url, message_to_user, false, nil, clear_cookies, ngx.HTTP_UNAUTHORIZED)
    end
    -- Блок кода по выводу окна ошибки (Конец)

    -- Функция сравнения адресов
    local function endsWith(str, suffix)
        return str:sub(-(#suffix)) == suffix
    end

    --Функция для конвертации ссылки в /logout-ссылку. Не добавляет /logout, если в ссылке уже есть /logout
    local function urlToLogoutUrl(url)
        if endsWith(url, '/logout') then
            return url
        end
        if endsWith(url, "/") then
            return url .. 'logout'
        else
            return url .. '/logout'
        end
    end

    -- Функция для работы со статическими файлами
    local function isStaticResource(url)
        local fragments = {}
        for fragment in string.gmatch(url, "/([^/]+)") do
            table.insert(fragments, fragment)
        end
        if (#fragments >= 2) then
            return fragments[2] == "static"
        else
            return false
        end
    end

    -- Функция проверки строки на то, что она пустая
    local function isEmptyString(str)
        return str == nil or str == ""
    end

    --Функция, возвращающая первый параметр, если он не пустой, или значение по умолчанию (второй параметр)
    local function ifStringPresentOrElse(value, default)
        if isNotEmptyString(value) then
            return value
        end
        return default
    end

    -- Функция проверки необходимых заголовков
    --suppress_error = true, если нужно игнорировать ошибку, не выводить errorWindow и не прерывать работу скрпита
    local function urlencode(str, update_url, suppress_errorWindow, err_msg)
        if str ~= nil and str ~= "" then
            str =
            string.gsub(
                    str,
                    "([^0-9a-zA-Z !'()*._~-])",
                    function(c)
                        return string.format("%%%02X", string.byte(c))
                    end
            )
            str = string.gsub(str, " ", "%%20")
            return str
        elseif suppress_errorWindow ~= true then
            ngx.update_time()
            ngx.log(ngx.ERR, "Передана пустая строка для приведения к URL-escape формату")
            err_msg = ifStringPresentOrElse(err_msg, "Передана пустая строка для приведения к URL-escape формату.")
            errorWindow(nil, err_msg, true, update_url, false, ngx.HTTP_BAD_REQUEST)
        end
        return ""
    end

    -- Функция перенаправления на смену пароля, если она запрошена в URI. ТОЛЬКО для запросов на /change_password
    local function redirectToPasswordChangeIfRequested(ngx_request_uri, ngx_server_name, keycloak_host, realm, service, opts_client_id)
        if isEmptyString(ngx_request_uri) or isEmptyString(ngx_server_name) or isEmptyString(keycloak_host)
                or isEmptyString(realm) or isEmptyString(service) or isEmptyString(opts_client_id) then
            return
        end
        if string.match(ngx_request_uri, "/change_password") then
            --//TODO требуется доработка в случае хранения пользователей локально в БД Keycloak без подклбченной федерации
            ngx.redirect(keycloak_host .. "/realms/" .. realm .. "/protocol/openid-connect/auth?client_id=" .. service ..
                    "&response_mode=fragment&response_type=code&prompt=login&scope=openid&kc_action=UPDATE_PASSWORD&redirect_uri=https://" ..
                    ngx_server_name .. "/" .. opts_client_id .. "/")
        end
    end

    -- Убираем мусор
    collectgarbage()
    -- Инициализируем переменные
    local env = getEnv('/etc/nginx/data.env')
    local ga_host = env['GA_HOST']
    local gaa_host = env['GAA_HOST']
    local gaf_host = env['GAF_HOST']
    local heartbeat_enabled = env["HEARTBEAT_ENABLED"]
    local keycloak_host = env['KEYCLOAK_HOST']
    local performance_logs = env['PERFORMANCE_LOGS']
    local realm = env['REALM']
    local http_request = http.new()
    local access = false
    local is_public_client = false
    -- Резервирование
    local ga_host_canary = env['GA_HOST_CANARY']
    local gaf_host_canary = env['GAF_HOST_CANARY']
    --Безопасный режим
    local alarm_service_host = env['ALARM_SERVICE']
    local alarm_view_service_host = env['ALARM_VIEW_SERVICE']
    local data_manager_host = env['DATA_MANAGER']
    local cspa_impexp_host = env['CSPA_IMPEXP']
    local cspa_hmi_backend_host = env['CSPA_HMI_BACKEND']
    local hmi_backend_host = env['HMI_BACKEND']
    local hmi_frontend_host = env["HMI_FRONTEND"]
    local sdku_knp_backend_host = env['SDKU_KNP_BACKEND']
    local sdku_vtor_host = env['SDKU_VTOR']
    local sdku_mkr_backend_host = env['SDKU_MKR_BACKEND']
    local sdku_mkr_view_service_host = env['SDKU_MKR_VIEW_SERVICE']
    local evo_scheduler_host = env['EVO_SCHEDULER']
    local hmi_frontend_hydrocyclone_host = env['HMI_FRONTEND_HYDROCYCLONE']
    -- Разграничение доступов по IP
    local client_limited_access = env['CLIENT_LIMITED_ACCESS']
    local ip_limited_access = env['IP_LIMITED_ACCESS']
    local endpoints_limited_access = env['ENDPOINTS_LIMITED_ACCESS']
    -- Заголовки
    -- Время жизни сессии по бездействию по умолчанию (далее по тексту значение подстовляется из настроек Keycloak)
    ngx.var.x_timeout_session = "600"
    ngx.var.previous_auth = ""
    ngx.var.password_exp = ""
    ngx.var.cp_uri = ""
    ngx.var.nginx_url = "https://" .. ngx.var.server_name
    ngx.var.user_groups = ""
    ngx.var.new_request = ""
    ngx.var.new_url = ""
    ngx.var.allow_patterns = ""
    ngx.var.forbidden_patterns = ""
    ngx.var.user_login = ""
    ngx.var.user_ip = ""
    ngx.var.security_signature = ""
    ngx.var.system_is_recovery = false
    ngx.var.visibility_zone = ""
    ngx.var.canary = ""
    local url_logout = ""
    local update_url = ""
    local ssl_status = false
    local headers = ngx.req.get_headers()
    local client_for_opts_information_json = ""
    local client_for_backend_information_json = ""
    local lua_clients_info_json = ""
    local lead_time = 0
    local redirect_url_custom = ""
    local ws_proto = ngx.var.arg_token
    ngx.var.user_ip = headers["X-REAL-IP"] or headers["X-FORWARDED-FOR"] or ngx.var.remote_addr or "0.0.0.0"
    --Аудит
    local execution_log = {}
    local user_login = ifStringPresentOrElse(headers["x-user-login"], "unknown")

    local function checking_network_availability(url)
        local res, err =
            http_request:request_uri(
            url,
            {
                method = "GET",
                headers = {
                    ["Content-Type"] = "application/json"
                },
                ssl_verify = ssl_status
            }
        )

        if not res then
            ngx.log(ngx.ERR, "Ошибка запроса сетевой доступности: " .. url)
            return "DOWN"
        end

        if res.status == 200 then
            return "UP"
        else
            return "DOWN"
        end
    end

    if (endsWith(keycloak_host, "/")) then
        keycloak_host = keycloak_host:sub(1, -2)
    end

    if ngx.var.request_uri == "/hmi-frontend-cspa?_AUTH_TEST=1" then
        local auth_status = {
            auth = "OK"
        }
        ngx.header.content_type = "application/json"
        ngx.say(cjson.encode(auth_status))
        ngx.status = 200
        return
    end

    if (ngx.var.request_uri == "/health") then
        local health = {
            status_nginx = "UP",
            network_availability_keycloak = checking_network_availability(keycloak_host .. "/realms/master/.well-known/openid-configuration"),
            network_availability_grant_access = checking_network_availability(ga_host .. "/v1/")
        }
        ngx.status = 200
        ngx.header.content_type = "application/json"
        ngx.say(cjson.encode(health))
        ngx.exit(ngx.HTTP_OK)
    end
    if ngx.var.http_referer == (ngx.var.nginx_url .. "/health") then
        ngx.exit(ngx.HTTP_OK)
    end

    local network_availability_keycloak = checking_network_availability(keycloak_host .. "/realms/master/.well-known/openid-configuration")

    --Безопасный режим
    if network_availability_keycloak == "DOWN" then
        --Обозначаем статус аварийного режима
        ngx.var.system_is_recovery = true
        --Указываем URL для wss
        if (ngx.var.request_uri == "/alarm-view-service/alarm") then
            ngx.var.new_url = alarm_view_service_host
            ngx.var.new_request = "/alarm"
        elseif (ngx.var.request_uri == "/alarm-view-service/gs-guide-websocket") then
            ngx.var.new_url = alarm_service_host
            ngx.var.new_request = "/gs-guide-websocket"
        elseif (ngx.var.request_uri == "/cspa_hmi_backend/v2/hotlink") then
            ngx.var.new_url = cspa_hmi_backend_host
            ngx.var.new_request = "/v2/hotlink"
        elseif (ngx.var.request_uri == "/cspa_hmi_backend/hotlink") then
            ngx.var.new_url = cspa_hmi_backend_host
            ngx.var.new_request = "/hotlink"
        elseif (ngx.var.request_uri == "/hmi-backend/v2/hotlink") then
            ngx.var.new_url = hmi_backend_host
            ngx.var.new_request = "/v2/hotlink"
        elseif (ngx.var.request_uri == "/hmi-backend/hotlink") then
            ngx.var.new_url = hmi_backend_host
            ngx.var.new_request = "/hotlink"
        elseif (ngx.var.request_uri == "/sdku-vtor/ws") then
            ngx.var.new_url = sdku_vtor_host
            ngx.var.new_request = "/ws"
        else
            --Подставляем заголовки
            ngx.var.user_groups = headers["x-user-groups"]
            ngx.var.user_id = headers["x-user-id"]
            ngx.var.user_login = headers["x-user-login"]
            ngx.var.user_fullname = headers["x-user-fullname"]
            --Парсим входящией запрос
            local name_service = string.gsub(ngx.var.request_uri, "([^/+])/.*", "%1")
            local uri_service = string.gsub(ngx.var.request_uri, "^/[^/]+", "")
            --Указываем uri и параметры
            ngx.var.new_request = uri_service
            --Указываем URL
            if name_service == "/alarm-service" then
                ngx.var.new_url = alarm_service_host
            elseif name_service == "/alarm-view-service" then
                ngx.var.new_url = alarm_view_service_host
            elseif name_service == "/cspa_hmi_backend" then
                ngx.var.new_url = cspa_hmi_backend_host
            elseif name_service == "/cspa-impexp" then
                ngx.var.new_url = cspa_impexp_host
            elseif name_service == "/data-manager" then
                ngx.var.new_url = data_manager_host
            elseif name_service == "/evo_scheduler" then
                ngx.var.new_url = evo_scheduler_host
            elseif name_service == "/grant-access" then
                ngx.var.new_url = ga_host
            elseif name_service == "/grant_access_audit" or name_service == "/grant-access-audit" then
                ngx.var.new_url = gaa_host
            elseif name_service == "/hmi-backend" then
                ngx.var.new_url = hmi_backend_host
            elseif name_service == "/hmi-frontend-cspa" then
                ngx.var.new_url = hmi_frontend_host
            elseif name_service == "/sdku-knp-backend" then
                ngx.var.new_url = sdku_knp_backend_host
            elseif name_service == "/sdku-vtor" then
                ngx.var.new_url = sdku_vtor_host
            elseif name_service == "/sdku-mkr-backend" then
                ngx.var.new_url = sdku_mkr_backend_host
            elseif name_service == "/sdku-mkr-view-service" then
                ngx.var.new_url = sdku_mkr_view_service_host
            end
        end
        ngx.log(ngx.WARN, "Аварийный режим: ", ngx.req.get_method() .. " запрос по адресу " .. ngx.var.new_url .. ngx.var.new_request)
    else
        local service = string.match(ngx.var.request_uri, "^/([^/?]+)")
        local serviceExchange = ""

        if ngx.var.http_referer ~= nil then
            local referel_url = ngx.var.http_referer
            local urlForReferer = "https://" .. ngx.var.server_name
            local urlForStyles = string.sub(referel_url, urlForReferer:len() + 1)
            serviceExchange = string.match(urlForStyles, "^/([^/?]+)")
        end

        -- все что в /static/ - статический контент. Обрабатыается как и любой другой запрос
        local isStatic = isStaticResource(ngx.var.request_uri);
        -- оставлено для совместимости. Ниакой модификации названия сервиса не требуется, берем из url
        local isLegacyStatic = false

        -- Работа со статическими файлами
        if not isStatic and
            ((string.find(ngx.var.request_uri, ".js$") or
            string.find(ngx.var.request_uri, ".css$") or
            string.find(ngx.var.request_uri, ".ttf$") or
            string.find(ngx.var.request_uri, ".ico$") or
            string.find(ngx.var.request_uri, ".wav$") or
            string.find(ngx.var.request_uri, ".png$") or
            string.find(ngx.var.request_uri, ".svg$") or
            string.find(ngx.var.request_uri, "config.json") or
            string.find(ngx.var.request_uri, ".mp3$")) and
            ngx.var.http_referer ~= nil) then
            isLegacyStatic = true;
        end

        -- Работа со статическими файлами
        if isLegacyStatic then
            local referel_url = ngx.var.http_referer
            local urlForReferer = "https://" .. ngx.var.server_name
            local urlForStyles = string.sub(referel_url, urlForReferer:len() + 1)
            service = string.match(urlForStyles, "^/([^/?]+)")
        end

        if service == nil or isEmptyString(service) then ngx.log(ngx.ERR, "Запрос без адресата: cервис равен nil")
        elseif (ngx.var.request_uri == "/") then ngx.log(ngx.ERR, "На вход пришел пустой request_uri")
        -- Определяем сервис адресат
        elseif service ~= "resources" and service ~= "realms" then
            -- Получаем информацию по сервису для которого получаем токен через opts ( clientId, secret, redirectUrl, backendFlag )
            if (isEmptyString(service) and ngx.var.request_uri == "/") then
                ngx.log(ngx.ERR, "На вход пришел пустой request_uri. Сервис равен nil. Входящий запрос не корректен")
            end

            local audience = service
            local audience_urlencoded = urlencode(audience, update_url, false, "Запрос отклонён: не известен целевой сервис")
            serviceExchange = ifStringPresentOrElse(serviceExchange, service)

            update_url = ngx.var.nginx_url .. "/" .. serviceExchange .. "/"

            -- Получение данных по клиентам. Повторные запрос в случае ребалансировки infinispan
            local lua_clients_info, error_lua_clients_info
            ngx.update_time()
            local begin = ngx.now() -- Фиксируем время первого запроса
            local count = 11 -- Максимально допустимое количество поторных запросов
            while count > 0 do
                lua_clients_info, error_lua_clients_info =
                    http_request:request_uri(ga_host ..
                        "/v1/clientsInformation?userService=" .. audience_urlencoded ..
                        "&userServiceExchange=" .. urlencode(serviceExchange, update_url, false, "Запрос отклонён: не указан сервис-отправитель. Отправленный запрос - " .. tostring(ngx.var.request_uri)),
                    {
                        method = "GET",
                        headers = {
                            ["Content-Type"] = "application/json"
                        },
                        ssl_verify = ssl_status
                    }
                )
                count = handle_retrying_by_response_status(lua_clients_info.status, count,"/clientsInformation: Задержка ответа, ожидаем дополнительно 1 секунду для повторного запроса")
            end
            ngx.log(ngx.DEBUG, "lua_clients_info.status: ", lua_clients_info.status)
            ngx.update_time() -- Фиксируем время получения информации информации
            lead_time = ngx.now() - begin
            ngx.log(ngx.DEBUG, "Request grant-access/v1/clientsInformation execution time: ", lead_time) -- Фиксируем в лог быстродействие запроса

            -- Обработка возможной ошибки по недоступности Grant Access
            if lua_clients_info.status == ngx.HTTP_SERVICE_UNAVAILABLE then
                ngx.log(ngx.ERR, "Ошибка запроса информации по клиентам (grant-access/v1/clientsInformation): ", ngx.HTTP_SERVICE_UNAVAILABLE)
                errorWindow(nil, 'При запросе информации по клиентам Nginx не получил ответ от Grant Access - сервис не доступен.', true, update_url, false, ngx.HTTP_SERVICE_UNAVAILABLE)
                return
            end

            lua_clients_info_json = cjson.decode(lua_clients_info.body)

            if lua_clients_info_json.message ~= nil then
                if string.find(lua_clients_info_json.message, "UnknownHostException: keycloak") then
                    ngx.log(ngx.ERR, "Ошибка запроса информации по клиентам: ", ngx.HTTP_SERVICE_UNAVAILABLE)
                    errorWindow(nil, "При запросе информации по клиентам Grant Access не получил ответ от KeyCloak - сервис не доступен.", true, update_url, false, ngx.HTTP_SERVICE_UNAVAILABLE)
                else
                    ngx.log(ngx.ERR, "Неизвестная ошибка запроса информации по клиентам: ", lua_clients_info_json.message)
                    errorWindow(nil, "При запросе информации по клиентам Nginx получил неизвестную ошибку от Grant Access.", true, update_url, false, ngx.HTTP_SERVICE_UNAVAILABLE)
                end
            end
            client_for_opts_information_json = lua_clients_info_json.referrer_client
            client_for_backend_information_json = lua_clients_info_json.target_client
            -- Получение данных по клиентам (конец)
            execution_log.get_clients_data = {
                    type = "get_clients_data",
                    referer = ngx.var.http_referer,
                    to_service = client_for_opts_information_json.client_id,
                    user_id = user_login,
                    uri = "GA/v1/clientsInformation",
                    lead_time = lead_time
                }

            if "userdata" == type(client_for_opts_information_json.redirect_urls) then
                local err_mess = 'Отсутствует ресурс для перенаправления. Проверьте конфигурацию сервиса ' .. tostring(client_for_opts_information_json.client_id)
                errorWindow(url_logout, err_mess, false, nil, false, ngx.HTTP_BAD_REQUEST)
            end
            redirect_url_custom = client_for_opts_information_json.redirect_urls[1]

            -- Генерируем ссылку для самостоятельной смены пароля пользователем
            ngx.var.cp_uri = "https://" .. ngx.var.server_name .. "/" .. serviceExchange .. "/change_password"

            ngx.log(ngx.DEBUG, "audience = ", audience)

            -- Забираем токен из запроса (если его прислали)
            local access_token = ifStringPresentOrElse(ws_proto, headers["X-SECURITY-SIGNATURE"])

            -- Endpoint для проверки токена с фронт-приложения
            if ngx.var.request_uri and string.find(ngx.var.request_uri, "/introspect", 1, true) then
                --Проверяем наличие токена в запросе
                if not access_token or access_token == "" then
                    ngx.status = ngx.HTTP_BAD_REQUEST
                    ngx.header["Content-Type"] = "application/json"
                    ngx.say(cjson.encode({ error = "token is missing" }))
                    ngx.exit(ngx.HTTP_BAD_REQUEST)
                end
                --Отправляем запрос на introspection endpoint Keycloak
                local response_introspect, error_introspect = http_request:request_uri(
                    keycloak_host .. "/realms/" .. realm .. "/protocol/openid-connect/token/introspect",
                    {
                        method = "POST",
                        headers = {
                            ["Content-Type"] = "application/x-www-form-urlencoded"
                        },
                        body = ngx.encode_args(
                            {
                                client_id = client_for_backend_information_json.client_id,
                                client_secret = client_for_backend_information_json.client_secret,
                                token = access_token
                            }
                        ),
                        ssl_verify = ssl_status
                    }
                )

                -- Проверяем, что HTTP-запрос вообще выполнился
                if not response_introspect then
                    -- Возвращаем ошибку, если запрос не удалось отправить
                    ngx.status = ngx.HTTP_INTERNAL_SERVER_ERROR
                    ngx.header["Content-Type"] = "application/json"
                    ngx.say(cjson.encode({ error = "introspection request failed", details = error_introspect }))
                    ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
                end

                -- Проверяем HTTP-статус ответа от Keycloak
                if response_introspect.status ~= ngx.HTTP_OK then
                    -- Пробрасываем статус и тело ответа Keycloak клиенту
                    ngx.status = response_introspect.status
                    ngx.header["Content-Type"] = "application/json"
                    ngx.say(response_introspect.body)
                    ngx.exit(response_introspect.status)
                end

                -- Парсим JSON-ответ от Keycloak
                local ok, data = pcall(cjson.decode, response_introspect.body)

                -- Проверяем, что JSON распарсился и является таблицей
                if not ok or type(data) ~= "table" then
                    ngx.status = ngx.HTTP_INTERNAL_SERVER_ERROR
                    ngx.header["Content-Type"] = "application/json"
                    ngx.say(cjson.encode({ error = "failed to parse introspection response" }))
                    ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
                end

                -- Возвращаем клиенту значение поля active из ответа Keycloak
                ngx.status = ngx.HTTP_OK
                ngx.header["Content-Type"] = "application/json"
                ngx.say(cjson.encode({ active = data.active }))
                ngx.exit(ngx.HTTP_OK)
            end

            -- Пустой секрет может быть только у публичного клиента. Доступ к такому предоставляется без дополнительных проверок
            if "userdata" == type(client_for_backend_information_json.client_secret) or isEmptyString(client_for_backend_information_json.client_secret) then
                ngx.log(ngx.DEBUG, "Обращение к публичному клиенту [" .. client_for_backend_information_json.client_id .. "] от [" .. client_for_opts_information_json.client_id .. "]")
                is_public_client = true
                access = true
                ngx.var.new_url = client_for_backend_information_json.description
                ngx.var.new_request = ngx.var.request_uri
                ngx.var.previous_auth = ifStringPresentOrElse(headers["X-USER-PREVIOUS_AUTH"], ngx.var.previous_auth)
                ngx.var.password_exp = ifStringPresentOrElse(headers["X-USER-PASSWORD_EXP"], ngx.var.password_exp)
                ngx.var.x_timeout_session = ifStringPresentOrElse(headers["X-TIMEOUT-SESSION"], ngx.var.x_timeout_session)
                ngx.var.cp_uri = ifStringPresentOrElse(headers["X-CP-URI"], ngx.var.cp_uri)
                ngx.var.user_fullname = ifStringPresentOrElse(headers["X-USER-FULLNAME"], ngx.var.user_fullname)
                ngx.var.user_groups = ifStringPresentOrElse(headers["X-USER-GROUPS"], ngx.var.user_groups)
                ngx.var.user_id = ifStringPresentOrElse(headers["X-USER-ID"], ngx.var.user_id)
                ngx.var.user_login = ifStringPresentOrElse(headers["X-USER-LOGIN"], ngx.var.user_login)
                ngx.var.user_ip = ifStringPresentOrElse(headers["X-USER-IP"], ngx.var.user_ip)
                ngx.var.allow_patterns = ifStringPresentOrElse(headers["X-USER-ALLOW-PATTERNS"], ngx.var.allow_patterns)
                ngx.var.forbidden_patterns = ifStringPresentOrElse(headers["X-USER-FORBIDDEN-PATTERNS"], ngx.var.forbidden_patterns)
                ngx.var.nginx_url = ifStringPresentOrElse(headers["X-NGINX-URI"], ngx.var.nginx_url)
                ngx .var.system_is_recovery = ifStringPresentOrElse(headers["SYSTEM_IS_RECOVERY"], ngx .var.system_is_recovery)
                ngx.var.security_signature = ifStringPresentOrElse(ws_proto, headers["X-SECURITY-SIGNATURE"])
                ngx.var.visibility_zone = ifStringPresentOrElse(headers["X-Visibility-Zone"], ngx.var.visibility_zone)
                ngx.var.canary = ifStringPresentOrElse(headers["X-SECURITY-CANARY"], ngx.var.canary)
                --Перенаправляем на смену пароля, если нужно
                redirectToPasswordChangeIfRequested(ngx.var.request_uri, ngx.var.server_name, keycloak_host, realm, service, client_for_opts_information_json.client_id)
                if isLegacyStatic then
                    ngx.var.new_url = client_for_opts_information_json.description
                    ngx.var.new_request = ngx.var.request_uri
                elseif isStatic then
                    ngx.var.new_url = client_for_opts_information_json.description
                    ngx.var.new_request = string.sub(ngx.var.request_uri, tostring(string.find(ngx.var.request_uri, "/", 2, true)))
                end
            elseif isNotEmptyString(access_token) then
                -- Валидация токена
                ngx.update_time()
                begin = ngx.now()
                local response_access, error_access = http_request:request_uri(
                    keycloak_host .. "/realms/" .. realm .. "/protocol/openid-connect/token/introspect",
                    {
                        method = "POST",
                        headers = {
                            ["Content-Type"] = "application/x-www-form-urlencoded"
                        },
                        body = ngx.encode_args(
                            {
                                client_id = client_for_backend_information_json.client_id,
                                client_secret = client_for_backend_information_json.client_secret,
                                token = access_token
                            }
                        ),
                        ssl_verify = ssl_status
                    }
                )
                ngx.update_time()
                lead_time = ngx.now() - begin
                ngx.log(ngx.DEBUG, "response keycloak/realms/" .. realm .. "/protocol/openid-connect/token/introspect execution time ", lead_time)

                if response_access.status == ngx.HTTP_SERVICE_UNAVAILABLE then
                    ngx.log(ngx.ERR, "Ошибка запроса Keycloak/realms/" .. realm .. "/protocol/openid-connect/token/introspect: ", ngx.HTTP_SERVICE_UNAVAILABLE)
                    errorWindow(nil, 'При проверке токена доступа Nginx не получил ответ от KeyCloak - сервис не доступен..', true, update_url, false, ngx.HTTP_SERVICE_UNAVAILABLE)
                    return
                end
                execution_log.introspect = {
                        type = "introspect",
                        referer = ngx.var.http_referer,
                        to_service = client_for_backend_information_json.client_id,
                        user_id = user_login,
                        uri = "KK/realms/master/protocol/openid-connect/token/introspect",
                        lead_time = lead_time
                    }

                local response_access_json = cjson.decode(response_access.body)

                if response_access_json.active and response_access_json.active == true then
                    if client_for_backend_information_json.backend then
                        -- Обмениваем токен, если флоу сервер-сервер (Начало)
                        ngx.update_time()
                        begin = ngx.now()
                        local exchange_token_response, error_access = http_request:request_uri(
                            keycloak_host .. "/realms/" .. realm .. "/protocol/openid-connect/token",
                            {
                                method = "POST",
                                headers = {
                                    ["Content-Type"] = "application/x-www-form-urlencoded"
                                },
                                body = ngx.encode_args(
                                    {
                                        client_id = client_for_backend_information_json.clientId,
                                        client_secret = client_for_backend_information_json.client_secret,
                                        grant_type = "urn:ietf:params:oauth:grant-type:token-exchange",
                                        subject_token_type = "urn:ietf:params:oauth:token-type:access_token",
                                        subject_token = access_token
                                    }
                                ),
                                ssl_verify = ssl_status
                            }
                        )
                        ngx.update_time()
                        lead_time = ngx.now() - begin
                        ngx.log(ngx.DEBUG, "Request Keycloak/realms/" .. realm .. "/protocol/openid-connect/token execution time ", lead_time)

                        if exchange_token_response.status == ngx.HTTP_SERVICE_UNAVAILABLE then
                            ngx.log(ngx.ERR, "Ошибка запроса Keycloak/realms/" .. realm .. "/protocol/openid-connect/token: ", ngx.HTTP_SERVICE_UNAVAILABLE)
                            errorWindow(nil, 'При запросе токена доступа Nginx не получил ответ от KeyCloak - сервис не доступен.', true, update_url, false, ngx.HTTP_SERVICE_UNAVAILABLE)
                            return
                        end
                        execution_log.exchange = {
                                type = "exchange",
                                referer = ngx.var.http_referer,
                                to_service = client_for_backend_information_json.client_id,
                                user_id = user_login,
                                uri = "KK/realms/master/protocol/openid-connect/token",
                                lead_time = lead_time
                            }
                        -- Обмениваем токен, если флоу сервер-сервер (Конец)

                        local exchange_token_response_json = cjson.decode(exchange_token_response.body)
                        access_token = exchange_token_response_json.access_token
                        ngx.var.security_signature = access_token
                    end
                else
                    -- Обработка некорректного токена
                    ngx.log(ngx.WARN, "Попытка обратится с невалидным токеном ", ngx.HTTP_UNAUTHORIZED)
                    errorWindow(url_logout, 'Токен доступа не валиден.', false, nil, false, ngx.HTTP_UNAUTHORIZED)
                end
            else
                -- Аутентификация или проверка уже Аутентифицированого пользователя происходин на основе библиотеки resty.openidc
                ngx.update_time()
                begin = ngx.now()
                -- Описываем opts для реализации протокола OpenID Connect
                local opts = {
                    redirect_uri = redirect_url_custom,
                    accept_none_alg = false,
                    ssl_verify = "no",
                    discovery = keycloak_host .. "/realms/" .. realm .. "/.well-known/openid-configuration",
                    client_id = client_for_opts_information_json.client_id,
                    client_secret = client_for_opts_information_json.client_secret,
                    scope = openid,
                    redirect_uri_scheme = "https",
                    logout_path = "/" .. client_for_opts_information_json.client_id .. "/logout_NOT_APPLICABLE",
                    revoke_tokens_on_logout = true,
                    redirect_after_logout_uri = ngx.var.nginx_url .. "/" .. client_for_opts_information_json.client_id .. "/",
                    redirect_after_logout_with_id_token_hint = false,
                    session_contents = {
                        id_token = true,
                        access_token = true,
                        user = true
                    }
                }
                local response_auth, error_auth, target, session = openidc.authenticate(opts)
                ngx.update_time()
                lead_time = ngx.now() - begin
                ngx.log(ngx.DEBUG, "response_auth execution time ", lead_time)
                execution_log.openidc = {
                        type = "openidc",
                        referer = ngx.var.http_referer,
                        to_service = client_for_opts_information_json.client_id,
                        user_id = user_login,
                        uri = "openidc.authenticate",
                        lead_time = lead_time
                    }

                if (isNotEmptyString(error_auth) and string.find(error_auth, "request to the redirect_uri")) then
                    if (session ~= nil) then
                        local ok, error_auth = session:destroy()
                        if (error_auth ~= nil or not ok) then
                            ngx.log(ngx.ERR, "Ошибка удаления старой сессии: ", ok, error_auth)
                        end
                    end
                    -- redirecting the home page here will result in a new redirect to login
                    return ngx.redirect(ngx.var.nginx_url .. "/" .. client_for_opts_information_json.client_id .. "/")
                end

                if not response_auth or response_auth.status == ngx.HTTP_SERVICE_UNAVAILABLE then
                    ngx.log(ngx.ERR, "Ошибка авторизации: ", error_auth)
                    errorWindow(nil, 'При авторизации Nginx не поличил ответ от KeyCloak - сервис не доступен', true, update_url, false, ngx.HTTP_SERVICE_UNAVAILABLE)
                    return
                end

                if response_auth and response_auth.access_token then
                    access_token = response_auth.access_token
                    ngx.var.security_signature = access_token
                end
            end

            if string.match(ngx.var.request_uri, "/logout") == "/logout" then
                -- Выход на страницу логина приложения, если нажали logout - logout флаг в true и запрос на grant-access
                url_logout = keycloak_host .. "/realms/" .. realm ..
                            "/protocol/openid-connect/logout?id_token_hint=" .. client_for_opts_information_json.id_token ..
                            "&post_logout_redirect_uri=https://" ..ngx.var.server_name .. "/" .. client_for_opts_information_json.client_id .. "/"

                -- Запрос в ГА при разлогине пользователя
                local ga_user_logout, error_logout
                ngx.update_time()
                count = 11 -- Максимально допустимое количество поторных запросов
                while count > 0 do
                    ga_user_logout, error_logout =
                        http_request:request_uri(ga_host .. "/v1/logout",
                        {
                            method = "GET",
                            headers = {
                                ["Content-Type"] = "applapplication/json",
                                ["X-SECURITY-SIGNATURE"] = access_token,
                                ["X-USER-IP"] = ngx.var.user_ip
                            },
                            ssl_verify = ssl_status
                        }
                    )
                    count = handle_retrying_by_response_status(ga_user_logout.status, count, "/logout: Задержка ответа, ожидаем дополнительно 1 секунду для повторного запроса")
                end
                ngx.update_time()
                ngx.log(ngx.DEBUG,"ga_user_logout.status: ",ga_user_logout.status)
                ngx.log(ngx.DEBUG, "logout execution time ", ngx.now() - begin)

                local newcookies = {}
                table.insert(newcookies, "session=deleted; Expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; HttpOnly; Secure")
                table.insert(newcookies, "session_2=deleted; Expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; HttpOnly; Secure")
                table.insert(newcookies, "session_3=deleted; Expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; HttpOnly; Secure")
                table.insert(newcookies, "JSESSIONID=deleted; Expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; HttpOnly; Secure")
                ngx.header.set_cookie = newcookies
                ngx.redirect(url_logout)
            end

            -- заполняем access_token для поддержки работы с публичными клиентами
            if isEmptyString(access_token) then
                if isNotEmptyString(ws_proto) then
                    access_token = ws_proto
                else access_token = headers["X-SECURITY-SIGNATURE"]
                end
            end
            if is_public_client == false and access_token and isNotEmptyString(access_token) then
                local nginxUri = string.sub(ngx.var.request_uri, string.len(audience) + 2)
                local nginxUriArgs = string.gsub(nginxUri, ".*?", "")
                nginxUri = string.gsub(nginxUri, "?.*", "")
                -- Получаем информацию по пользователю
                if isEmptyString(nginxUri) then
                    nginxUri = "/"
                end

                -- Работа со статическими файлами
                if isLegacyStatic then
                    access = true
                    ngx.var.new_url = client_for_opts_information_json.description
                    ngx.var.new_request = ngx.var.request_uri
                    -- Канарейка для статики (Начало)
                    local canary, err = get_attr_from_jwt(access_token, "canary")
                    if canary and canary == "true" then
                        ngx.log(ngx.DEBUG, "Canary static start: " .. ngx.var.new_url .. ngx.var.new_request)
                        --Проверка GAF
                        if ngx.var.new_url:sub(1, #gaf_host) == gaf_host then
                            ngx.var.new_url = gaf_host_canary .. ngx.var.new_url:sub(#gaf_host + 1)
                        end
                        ngx.log(ngx.DEBUG, "Canary static finish: " .. ngx.var.new_url .. ngx.var.new_request)
                    end
                    --Канарейка для статики (Конец)
                else
                    -- Фиксируем в лог быстродействие запроса
                    -- Получаем данные по пользователю и его доступам
                    if audience_urlencoded == "" then
                        ngx.log(ngx.WARN, "Попытка проверки доступа без указания имени(id) сервиса. Request: " .. ngx.var.request .. ", referrer: " .. ngx.var.Referer)
                    end

                    -- Проверка разрешений пользователя на доступ
                    local userInformation, error_userInformation
                    ngx.update_time()
                    begin = ngx.now()
                    count = 11 -- Максимально допустимое количество поторных запросов
                    while count > 0 do
                        userInformation, error_userInformation =
                            http_request:request_uri(ga_host ..
                                "/v1/userPermissions?userService=" .. audience_urlencoded ..
                                "&requestUri=" .. urlencode(nginxUri, update_url, false, "Ошибка с адресом Nginx ( " .. tostring(nginxUri) .. ")") ..
                                "&logout=false&requestType=" .. ngx.req.get_method(),
                            {
                                method = "GET",
                                headers = {
                                    ["Content-Type"] = "applapplication/json",
                                    ["X-SECURITY-SIGNATURE"] = access_token,
                                    ["X-USER-IP"] = ngx.var.user_ip
                                },
                                ssl_verify = ssl_status
                            }
                        )
                        count = handle_retrying_by_response_status(userInformation.status, count, "/userPermissions: Задержка ответа, ожидаем дополнительно 1 секунду для повторного запроса")
                    end
                    ngx.update_time()
                    lead_time = ngx.now() - begin
                    ngx.log(ngx.DEBUG, "Request grant-access/v1/userPermissions execution time ", lead_time)

                    if userInformation.status == ngx.HTTP_SERVICE_UNAVAILABLE then
                        ngx.log(ngx.ERR, "Ошибка запроса grant-access/v1/userPermissions: ", ngx.HTTP_SERVICE_UNAVAILABLE)
                        errorWindow(nil, 'При проверке пользовательских доступов Nginx не получил ответ от Grant Access - сервис не доступен.', true, update_url, false, ngx.HTTP_SERVICE_UNAVAILABLE)
                        return
                    end

                    ngx.log(ngx.DEBUG,"userInformation.status: ",userInformation.status)
                    local user_information_json = cjson.decode(userInformation.body)

                    -- Добавляем заголовоки X-USER-ID и X-USER-FULLNAME
                    ngx.var.user_fullname = user_information_json.userFullName
                    ngx.var.user_id = user_information_json.userId
                    ngx.var.user_login = user_information_json.userLogin

                    -- Пробрасываем heartbeat для GA
                    if (ngx.var.request_uri == "/grant-access/v1/sessions/heartbeat") then
                        if (heartbeat_enabled == "true") then
                            access = true
                            ngx.var.new_url = ga_host
                            ngx.var.new_request = string.gsub(ngx.var.request_uri, "^/[^/]+", "")
                            if isNotEmptyString(ws_proto) then
                                ngx.var.security_signature = ws_proto
                            else ngx.var.security_signature = headers["X-SECURITY-SIGNATURE"]
                            end
                            ngx.var.user_groups = urlencode(user_information_json.groupsByUser, update_url, true, nil)
                        else
                            ngx.log(ngx.WARN, "Received heartbeat request but GA /heartbeat is disabled!")
                            return
                        end
                    else
                        if user_information_json.message~=nil and string.find(user_information_json.message, 'UnknownHostException: keycloak') then
                            ngx.log(ngx.ERR, "Ошибка запроса от Grant access к Keycloak: ", ngx.HTTP_SERVICE_UNAVAILABLE)
                            errorWindow(nil, 'При запросе пользовательских доступов Grant Access не получил ответ от KeyCloak - сервис не доступен.', true, update_url, false, ngx.HTTP_SERVICE_UNAVAILABLE)
                            return
                        end

                        -- Проверяем лимит жизни сессии
                        if (user_information_json.invalidateByLifetime) then
                            ngx.log(ngx.DEBUG, "Session lifetime expired: " .. tostring(user_information_json.userId) .. " --- " .. tostring(user_information_json.userLogin))
                            invalidate_session_from_grant_access(update_url, "Время вашей сессии истекло. Необходимо зайти в систему заново", true)
                        end
                        -- Проверяем таймаут неактивност сессии
                        if (user_information_json.invalidateByInactivity) then
                            ngx.log(ngx.DEBUG, "Session SSO timeout expired: " .. tostring(user_information_json.userId) .. " --- " .. tostring(user_information_json.userLogin))
                            invalidate_session_from_grant_access(update_url, "Ваша сессия была завершена из-за неактивности. Необходимо зайти в систему заново", true)
                        end
                        -- Проверяем хартбит сессии
                        if (heartbeat_enabled == "true") then
                            if (user_information_json.invalidateByHeartbeat) then
                                ngx.log(ngx.DEBUG, "Session heartbeat expired: " .. tostring(user_information_json.userId) .. " --- " .. tostring(user_information_json.userLogin))
                                invalidate_session_from_grant_access(update_url, "Вы слишком долго отсутствовали в системе. Необходимо зайти в систему заново", true)
                            end
                        end
                        -- Проверяем запрет доступа
                        if (user_information_json.access == false) then
                            ngx.log(ngx.DEBUG, "Сессия завершена: " .. tostring(user_information_json.userId) .. " --- " .. tostring(user_information_json.userLogin))
                            errorWindow(urlToLogoutUrl(update_url), 'Доступ запрещён.', false, nil, false, ngx.HTTP_FORBIDDEN) -- с кнопкой Выход
                            return
                        end

                        execution_log.permissions = {
                                type = "permissions",
                                referer = ngx.var.http_referer,
                                to_service = client_for_opts_information_json.client_id,
                                user_id = user_login,
                                uri = "GA/v1/userPermissions",
                                lead_time = lead_time
                            }

                        --Проверяем настройки сессии
                        --Запрашиваем список административных групп
                        local policy_response, policy_error
                        ngx.update_time()
                        local begin = ngx.now()
                        local count = 11 -- Максимальное количество повторных запросов

                        while count > 0 do
                            policy_response, policy_error =
                                http_request:request_uri(ga_host .. "/v1/policy/realmAttribute?realm=" .. realm,
                                {
                                    method = "GET",
                                    headers = {
                                        ["Content-Type"] = "application/json",
                                        ["X-SECURITY-SIGNATURE"] = access_token,
                                        ["X-USER-IP"] = ngx.var.user_ip
                                    },
                                    ssl_verify = ssl_status
                                }
                            )
                            count = handle_retrying_by_response_status(policy_response.status, count, "/v1/policy/realmAttribute: Задержка ответа, ожидаем дополнительно 1 секунду для повторного запроса")
                        end

                        ngx.log(ngx.DEBUG, "-----policy_response.status: ", policy_response.status)
                        ngx.update_time()
                        lead_time = ngx.now() - begin
                        ngx.log(ngx.DEBUG, "Request /v1/policy/realmAttribute execution time: ", lead_time)

                        -- Обработка ошибки недоступности сервиса
                        if policy_response.status == ngx.HTTP_SERVICE_UNAVAILABLE then
                            ngx.log(ngx.ERR, "Ошибка запроса политик (Grant Access: v1/policy/realmAttribute): ", ngx.HTTP_SERVICE_UNAVAILABLE)
                            errorWindow(nil, 'При запросе политик Nginx не получил ответ от Grant Access - сервис не доступен.', true, update_url, false, ngx.HTTP_SERVICE_UNAVAILABLE)
                        end

                        -- Парсим JSON-ответ
                        local policy_json = cjson.decode(policy_response.body)

                        if policy_json.adminPasswordPolicyGroup and type(policy_json.adminPasswordPolicyGroup) == "table" then
                            local found = true
                            for _, value in ipairs(policy_json.adminPasswordPolicyGroup) do
                                if value == user_information_json.groupsByUser then
                                    found = false
                                    -- Группа совпала – используем таймаут администратора
                                    if user_information_json.sessionTimeoutSSOAdmin then
                                        ngx.var.x_timeout_session = user_information_json.sessionTimeoutSSOAdmin
                                    else
                                        ngx.log(ngx.WARN, "sessionTimeoutSSOAdmin не задан, оставляем текущий таймаут: " .. ngx.var.x_timeout_session)
                                    end
                                    break
                                end
                            end

                            if found then
                                -- Группа не найдена – таймаут обычного пользователя
                                if user_information_json.sessionTimeoutSSO then
                                    ngx.var.x_timeout_session = user_information_json.sessionTimeoutSSO
                                else
                                    ngx.log(ngx.WARN, "Ошибка запроса настроек сессии, будет использовано значение по умолчанию: " ..
                                            ngx.var.x_timeout_session .. " секунд")
                                end
                            end
                        else
                            -- Поле adminPasswordPolicyGroup отсутствует или равно null (или не массив)
                            ngx.log(ngx.WARN, "Поле adminPasswordPolicyGroup отсутствует или не является массивом, используем таймаут по умолчанию")
                            if user_information_json.sessionTimeoutSSO then
                                ngx.var.x_timeout_session = user_information_json.sessionTimeoutSSO
                            else
                                ngx.log(ngx.WARN, "sessionTimeoutSSO тоже не задан, таймаут остаётся прежним: " .. ngx.var.x_timeout_session)
                            end
                        end

                        --Форматируем дату последнего входа
                        local dateTimestamp = user_information_json.lastLoginTime
                        if isNotEmptyString(dateTimestamp) and nil ~= tonumber(dateTimestamp) then
                            local date = os.date("*t", math.floor(tonumber(dateTimestamp) / 1000))
                            local lastLoginTime =
                                string.format(
                                "%04d-%02d-%02d %02d:%02d:%02d.%03d",
                                date.year,
                                date.month,
                                date.day,
                                date.hour + 3, --приводится к московскому времени (Требования ТНТ)
                                date.min,
                                date.sec,
                                dateTimestamp % 1000
                            )
                            ngx.var.previous_auth = lastLoginTime
                        end

                        -- Установка срока действия пароля
                        if isNotEmptyString(user_information_json.passwordExpireDays) then
                            if user_information_json.passwordExpireDays ~= "-1" then
                                ngx.var.password_exp = user_information_json.passwordExpireDays
                            end
                        end

                        -- Ограничение смены пароля пользователя самостоятельно в течении 2-х дней //TODO в дальнейшем сделать настраиваемым параметром
                        if isNotEmptyString(user_information_json.pwdDataChange) then
                            local pwd_time = user_information_json.pwdDataChange
                            local current_time = os.time(os.date("!*t"))
                            --TODO: делим на 1000, чтобы уйти от миль и прийти к секундам. Убрать после лечения бага в плагинах
                            local last_pwd_time = math.floor(pwd_time / 1000) + 172800
                            --Самостоятельная смена пароля пользователем
                            if string.match(ngx.var.request_uri, "/change_password") then
                                if last_pwd_time < current_time then
                                    redirectToPasswordChangeIfRequested(ngx.var.request_uri, ngx.var.server_name, keycloak_host, realm, service, client_for_opts_information_json.client_id)
                                else
                                    local change_password_false_url = "https://" .. ngx.var.server_name .. "/" .. client_for_opts_information_json.client_id .. "/"
                                    ngx.status = ngx.HTTP_FORBIDDEN
                                    -- Генерируем nonce и ставим CSP. Указываем необходимые заголовки.
                                    local nonce = make_nonce()
                                    local csp = table.concat({
                                        "default-src 'none';", -- По умолчанию запрещаем загрузку всего
                                        "script-src 'self' 'nonce-" .. nonce .. "';", -- разрешаем только script с nonce
                                        "style-src 'self' 'nonce-" .. nonce .. "';", -- разрешаем только style с nonce
                                        "img-src 'self' data:;", --Разрешаем изображения с того же источника и data: URI (встроенные изображения)
                                        "connect-src 'self';", -- Разрешаем XHR/fetch/websocket только к тому же origin
                                        "font-src 'self';", -- Разрешаем подгружать шрифты только с того же origin
                                        "frame-ancestors 'none';", -- Запрещаем встраивание страницы в iframe/frames
                                        "base-uri 'none';", -- Запрещаем использование тега <base>, чтобы нельзя было менять базовый URL для ссылок/ресурсов
                                        "form-action 'self';", -- Разрешаем отправку форм только на тот же origin
                                        "object-src 'none';" --Запрещает загрузку и использование плагин‑типа ресурсов через теги <object>, <embed> и <applet> из любых источников.
                                    }, " ")
                                    ngx.header["Content-Security-Policy"] = csp -- Устанавливаем заголовок Content-Security-Policy в ответ
                                    ngx.header["X-Content-Type-Options"] = "nosniff" -- Запрещаем браузеру пытаться угадывать MIME‑тип (защищает от некоторых атак / XSS через неправильный Content-Type)
                                    ngx.header["X-Frame-Options"] = "DENY" -- Дополнительная защита от встраивания в iframe (можно опустить, если уже используете frame-ancestors в CSP)
                                    ngx.header["Referrer-Policy"] = "no-referrer-when-downgrade" -- Не посылать Referer при работе по HTTP
                                    ngx.header["Content-Type"] = "text/html; charset=utf-8"
                                    ngx.say(
                                            '<html>' ..
                                                    '<head>' ..
                                                    '<meta charset="utf-8">' ..
                                                    '<title>Доступ запрещен</title>' ..
                                                    '</head>' ..
                                                    '<body>' ..
                                                    '<p style="text-align: center;"><strong>Доступ запрещен.</strong></p>' ..
                                                    '<p style="text-align: center;"><strong>С последней смены пароля прошло менее двух дней.</strong></p>' ..
                                                    '<script nonce="' .. nonce .. '">' ..
                                                    'setTimeout(function(){window.location.href="' .. js_string_escape(change_password_false_url) .. '"}, 10000);' ..
                                                    '</script>' ..
                                                    '</body>' ..
                                                    '</html>'
                                    )
                                    ngx.exit(ngx.status)
                                end
                            end
                        else
                            -- Перенаправление пользователя на смену пароля при необходимости
                            redirectToPasswordChangeIfRequested(ngx.var.request_uri, ngx.var.server_name, keycloak_host, realm, service, client_for_opts_information_json.client_id)
                        end

                        local json_user =
                            cjson.encode {
                            login = user_information_json.userLogin,
                            fullname = ngx.var.user_fullname,
                            user_id = ngx.var.user_id,
                            uri = ngx.var.request_uri
                        }

                        access = user_information_json.access
                        if access == true then
                            ngx.var.new_url = user_information_json.redirectUrl
                            if (string.find(nginxUriArgs, "=")) then
                                ngx.var.new_request = ngx.var.new_request .. "?" .. nginxUriArgs
                            end

                            -- Логирование
                            ngx.log(ngx.DEBUG, "Доступ предоставлен, пользователь: ", json_user)

                            -- Перенаправление пользователя на смену пароля
                            if string.match(ngx.var.request_uri, "/changePasswordByButton") == "/changePasswordByButton" then
                                ngx.redirect(keycloak_host .. "/realms/" .. realm .. "/protocol/openid-connect/auth?response_type=code&client_id=" ..
                                    client_for_opts_information_json.client_id .. "&redirect_uri=" .. redirect_url_custom .. "&kc_action=UPDATE_PASSWORD")
                            end

                            -- Канарейка (Начало)
                            local canary = user_information_json.canary
                            if canary and canary == "true" then
                                ngx.log(ngx.DEBUG, "Canary start: " .. ngx.var.new_url .. ngx.var.new_request)
                                --Проверка GA
                                if ngx.var.new_url:sub(1, #ga_host) == ga_host then
                                    ngx.var.new_url = ga_host_canary .. ngx.var.new_url:sub(#ga_host + 1)
                                end
                                --Проверка GAF
                                if ngx.var.new_url:sub(1, #gaf_host) == gaf_host then
                                    ngx.var.new_url = gaf_host_canary .. ngx.var.new_url:sub(#gaf_host + 1)
                                end
                                ngx.log(ngx.DEBUG, "Canary finish: " .. ngx.var.new_url .. ngx.var.new_request)
                            end
                            --Канарейка (Конец)

                            ngx.var.user_groups = urlencode(user_information_json.groupsByUser, update_url, true, nil)
                            ngx.var.allow_patterns = cjson.encode(user_information_json.allowedPatterns)
                            ngx.var.forbidden_patterns = cjson.encode(user_information_json.forbiddenPatterns)
                            ngx.var.user_fullname = urlencode(ngx.var.user_fullname, update_url, false, "Ошибка приведения ФИО к URL-escape формату: ФИО не указано")
                            ngx.var.visibility_zone = ifStringPresentOrElse(user_information_json.visibilityZone, "")
                            ngx.var.canary = ifStringPresentOrElse(user_information_json.canary, "")

                            if isEmptyString(ngx.var.security_signature) then
                                if isNotEmptyString(ws_proto) then
                                    ngx.var.security_signature = ws_proto
                                else ngx.var.security_signature = headers["X-SECURITY-SIGNATURE"]
                                end
                            end
                        else
                            ngx.log(ngx.DEBUG, "Доступ запрещен: ", json_user)
                        end
                    end
                end
            end
        else
            access = true
            ngx.var.new_url = keycloak_host
            ngx.var.new_request = ngx.var.request_uri
        end

        -- Запрет вызова определенных endpoints с некорректным ip на определенные сервисы
        -- (на основе параметров CLIENT_LIMITED_ACCESS,IP_LIMITED_ACCESS,ENDPOINTS_LIMITED_ACCESS)
        local arr_ip = split(ip_limited_access)
        local arr_client = split(client_limited_access)
        local arr_endpoints = split(endpoints_limited_access)
        local access_check = false
        for i_service, v_service in ipairs(arr_client) do
            for i_endpoint, v_endpoint in ipairs(arr_endpoints) do
                --совпадение по endpint и адресу client
                if (v_service .. v_endpoint == string.gsub(ngx.var.new_request, "%?.*", "")) then
                    for i_ip, v_ip in ipairs(arr_ip) do
                        --совпадение по IP
                        if (ngx.var.user_ip == v_ip) then
                            access_check = true
                        end
                    end

                    if (access_check == false) then
                        access = false
                        ngx.log(ngx.WARN,
                            "Доступ к ресурсу: " .. v_service .. v_endpoint .. " с ip адреса: " .. ngx.var.user_ip .. " запрещен")
                    end
                end
            end
        end

        ngx.update_time()
        lead_time = ngx.now() - start_time_request

        execution_log.total = {
            type = "total",
            referer = ngx.var.http_referer,
            to_service = ngx.var.new_url,
            user_login = ngx.var.user_login,
            uri = ngx.var.new_request,
            lead_time = lead_time
        }

        if performance_logs == "true" and not isLegacyStatic and not isStatic then
            ngx.log(ngx.NOTICE, "Итог обработки запроса в Nginx: " .. cjson.encode(execution_log))
        end

        -- Дебаг --
        -- ngx.log(ngx.NOTICE, "URL конечного адреса \nngx.var.new_url: ", ngx.var.new_url
        -- .. "\n ngx.var.new_request: " .. ngx.var.new_request
        -- .. "\n Заголовки:{"
        -- .. "\nngx.var.user_fullname: " .. ngx.var.user_fullname
        -- .. "\n, ngx.var.user_groups: " .. ngx.var.user_groups
        -- .. "\n, ngx.var.user_id: " .. ngx.var.user_id
        -- .. "\n, ngx.var.user_login: " .. ngx.var.user_login
        -- .. "\n, ngx.var.user_ip: " .. ngx.var.user_ip
        -- .. "\n, ngx.var.previous_auth: " .. ngx.var.previous_auth
        -- .. "\n, ngx.var.password_exp: " .. ngx.var.password_exp
        -- .. "\n, ngx.var.security_signature: " .. ngx.var.security_signature
        -- .. "\n, ngx.var.x_timeout_session: " .. ngx.var.x_timeout_session
        -- .. "\n, ngx.var.nginx_url: " .. ngx.var.nginx_url
        -- .. "\n}")

        if access == nil or access == false then
            errorWindow(urlToLogoutUrl(update_url), 'Доступы отозваны', false, update_url, false, ngx.HTTP_FORBIDDEN)
        end
    end
end
