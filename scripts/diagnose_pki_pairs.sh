#!/usr/bin/env bash
# Read-only diagnostics on the Execution Node; never prints private key data.
set +x
set -uo pipefail

usage() {
  cat <<'HELP'
Проверка сохранённых пар leaf.key/leaf.crt на Execution Node.
Запуск: sudo bash scripts/diagnose_pki_pairs.sh [--password-stdin] [каталог]
По умолчанию: /var/lib/platform-installer/execution/pki
Можно указать корень PKI, каталог проекта или отдельного запроса.
Выводятся даты файлов и проверяется keystore.p12. Файлы не изменяются.
Пароль PKCS12 вводится скрыто через терминал, один раз для всех запросов.
--password-stdin: прочитать пароль одной строкой из stdin вместо терминала.
Закрытые ключи и пароли в отчёт не попадают.
MATCH — пара совпадает; MISMATCH — разные открытые ключи;
ERROR — проверить пару не удалось (это не доказательство несовпадения).
Код выхода: 0 — все пары совпадают, 1 — несовпадение/ошибка пары,
2 — ошибка запуска, поиска или отсутствие пар.
HELP
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
  usage
  exit 0
fi
store_password=''
store_password_set=0
trap 'unset store_password' EXIT
if [[ ${1:-} == --password-stdin ]]; then
  if ! IFS= read -r store_password; then
    printf 'ERROR: пароль должен поступить одной строкой через stdin\n' >&2
    exit 2
  fi
  store_password_set=1
  shift
fi
if (( $# > 1 )); then
  usage >&2
  exit 2
fi

root=${1:-/var/lib/platform-installer/execution/pki}
if [[ ! -d "$root" || -L "$root" || ! -r "$root" || ! -x "$root" ]]; then
  printf 'ERROR: каталог недоступен или является ссылкой: %q\n' "$root" >&2
  exit 2
fi
for tool in openssl sha256sum find sort stat; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf 'ERROR: отсутствует команда %s\n' "$tool" >&2
    exit 2
  fi
done
if command -v cmp >/dev/null 2>&1; then
  printf 'CMP: доступен\n'
else
  printf 'CMP: отсутствует; проверка Installer через cmp могла завершиться технической ошибкой\n'
fi

read_store_password() {
  local store=$1
  if (( store_password_set == 0 )); then
    # Accept empty-password stores without prompting. Never put a password in
    # argv, environment or a temporary file; OpenSSL reads it from a pipe.
    if printf '\n' | openssl pkcs12 -in "$store" -passin stdin -noout >/dev/null 2>&1; then
      return 0
    fi
    printf 'Пароль keystore.p12 (ввод скрыт, в отчёт не записывается): ' >&2
    if ! IFS= read -r -s store_password </dev/tty; then
      printf '\nKEYSTORE_ERROR: пароль недоступен; используйте терминал или --password-stdin\n' >&2
      return 1
    fi
    printf '\n' >&2
    store_password_set=1
  fi
}

check_store() {
  local directory=$1 key_hash=$2 cert_hash=$3 store_key store_public store_cert leaf_cert issues=0
  local store="$directory/keystore.p12"
  if [[ ! -f "$store" || -L "$store" || ! -r "$store" ]]; then
    printf 'KEYSTORE_ERROR: keystore.p12 отсутствует, недоступен или является ссылкой\n'
    return 1
  fi
  read_store_password "$store" || return 1
  if ! printf '%s\n' "$store_password" | openssl pkcs12 -in "$store" -passin stdin -noout >/dev/null 2>&1; then
    printf 'KEYSTORE_ERROR: неверный пароль, повреждённый или неподдерживаемый PKCS12\n'
    return 1
  fi
  if ! store_cert=$(printf '%s\n' "$store_password" |
      openssl pkcs12 -in "$store" -passin stdin -clcerts -nokeys 2>/dev/null |
      openssl x509 -outform DER 2>/dev/null | sha256sum) ||
     ! store_public=$(printf '%s\n' "$store_password" |
      openssl pkcs12 -in "$store" -passin stdin -clcerts -nokeys 2>/dev/null |
      openssl x509 -pubkey -noout 2>/dev/null |
      openssl pkey -pubin -outform DER 2>/dev/null | sha256sum) ||
     ! store_key=$(printf '%s\n' "$store_password" |
      openssl pkcs12 -in "$store" -passin stdin -nocerts -nodes 2>/dev/null |
      openssl pkey -passin pass: -pubout -outform DER 2>/dev/null | sha256sum); then
    printf 'KEYSTORE_ERROR: не удалось разобрать конечный сертификат или ключ PKCS12\n'
    return 1
  fi
  printf 'KEYSTORE_CERT_PUBLIC_SHA256: %s\nKEYSTORE_KEY_PUBLIC_SHA256:  %s\n' "${store_public%% *}" "${store_key%% *}"
  if [[ "$store_public" == "$store_key" ]]; then
    printf 'KEYSTORE_INTERNAL_MATCH: ключ и сертификат внутри PKCS12 совпадают\n'
  else
    printf 'KEYSTORE_INTERNAL_MISMATCH: ключ и сертификат внутри PKCS12 различаются\n'
    issues=1
  fi
  if [[ -z "$key_hash" ]]; then
    printf 'KEYSTORE_KEY_UNAVAILABLE: leaf.key не проверен\n'
    issues=1
  elif [[ "$store_key" == "$key_hash" ]]; then
    printf 'KEYSTORE_KEY_MATCH: ключ PKCS12 соответствует leaf.key\n'
  else
    printf 'KEYSTORE_KEY_MISMATCH: ключ PKCS12 отличается от leaf.key\n'
    issues=1
  fi
  if [[ -n "$cert_hash" ]] && leaf_cert=$(openssl x509 -in "$directory/leaf.crt" -outform DER 2>/dev/null | sha256sum); then
    printf 'CERT_DER_SHA256:          %s\nKEYSTORE_CERT_DER_SHA256: %s\n' "${leaf_cert%% *}" "${store_cert%% *}"
    if [[ "$store_cert" == "$leaf_cert" ]]; then
      printf 'KEYSTORE_CERT_MATCH: сертификат PKCS12 идентичен leaf.crt\n'
    else
      printf 'KEYSTORE_CERT_MISMATCH: сертификат PKCS12 отличается от leaf.crt\n'
      issues=1
    fi
  else
    printf 'KEYSTORE_CERT_UNAVAILABLE: leaf.crt не проверен\n'
    issues=1
  fi
  return "$issues"
}

check_pair() {
  local directory=$1 key_hash='' cert_hash='' file issues=0
  printf '\nREQUEST: %q\n' "$directory"
  for file in leaf.key leaf.crt request-fingerprint keystore.p12 truststore.p12; do
    printf 'FILE: %q\n' "$file"
    if [[ ! -f "$directory/$file" || -L "$directory/$file" || ! -r "$directory/$file" ]]; then
      printf 'METADATA_UNAVAILABLE: отсутствует, недоступен или является ссылкой\n'
    elif ! stat -c '  modified=%y | changed=%z | size=%s | mode=%a | uid=%u | gid=%g' -- "$directory/$file"; then
      printf 'METADATA_ERROR\n'
      issues=1
    fi
  done
  # SPKI DER normalizes public-key encoding; pipefail rejects an OpenSSL error
  # instead of accepting the SHA256 of empty output. Empty passin prevents prompts.
  if [[ ! -f "$directory/leaf.key" || -L "$directory/leaf.key" ]] ||
     ! key_hash=$(openssl pkey -in "$directory/leaf.key" -passin pass: -pubout -outform DER </dev/null 2>/dev/null | sha256sum); then
    printf 'ERROR: не удалось прочитать leaf.key (формат, шифрование или доступ)\n'
    key_hash=''
    issues=1
  fi
  if [[ ! -f "$directory/leaf.crt" || -L "$directory/leaf.crt" ]] ||
     ! cert_hash=$(openssl x509 -in "$directory/leaf.crt" -pubkey -noout </dev/null 2>/dev/null |
                   openssl pkey -pubin -outform DER 2>/dev/null | sha256sum); then
    printf 'ERROR: не удалось прочитать открытый ключ leaf.crt\n'
    cert_hash=''
    issues=1
  fi
  printf 'KEY_PUBLIC_SHA256:  %s\nCERT_PUBLIC_SHA256: %s\n' "${key_hash%% *}" "${cert_hash%% *}"
  if [[ -n "$key_hash" && -n "$cert_hash" && "$key_hash" == "$cert_hash" ]]; then
    printf 'MATCH: ключ соответствует сертификату\n'
  elif [[ -n "$key_hash" && -n "$cert_hash" ]]; then
    printf 'MISMATCH: ключ не соответствует сертификату\n'
    issues=1
  fi
  check_store "$directory" "$key_hash" "$cert_hash" || issues=1
  return "$issues"
}

# NUL delimiters also handle spaces/newlines in operator-supplied paths.
# Do not follow directory symlinks. Discover either file to detect partial pairs.
find "$root" \( -name leaf.key -o -name leaf.crt \) -printf '%h\0' | sort -zu | (
  total=0
  issues=0
  while IFS= read -r -d '' directory; do
    ((total += 1))
    if ! check_pair "$directory"; then
      ((issues += 1))
    fi
  done
  printf '\nSUMMARY: пар=%d, проблем=%d\n' "$total" "$issues"
  if (( total == 0 )); then
    printf 'ERROR: пары leaf.key/leaf.crt не найдены\n'
    exit 2
  fi
  (( issues == 0 ))
)
statuses=("${PIPESTATUS[@]}")
if (( statuses[0] != 0 || statuses[1] != 0 )); then
  printf 'ERROR: поиск завершился с ошибкой; список пар может быть неполным\n' >&2
  exit 2
fi
exit "${statuses[2]}"
