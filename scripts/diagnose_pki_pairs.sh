#!/usr/bin/env bash
# Read-only diagnostics on the Execution Node; never prints private key data.
set +x
set -uo pipefail

usage() {
  cat <<'HELP'
Проверка сохранённых пар leaf.key/leaf.crt на Execution Node.
Запуск: sudo bash scripts/diagnose_pki_pairs.sh [каталог]
По умолчанию: /var/lib/platform-installer/execution/pki
Можно указать корень PKI, каталог проекта или отдельного запроса.
Файлы не изменяются; закрытые ключи и пароли не выводятся и не запрашиваются.
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
if (( $# > 1 )); then
  usage >&2
  exit 2
fi

root=${1:-/var/lib/platform-installer/execution/pki}
if [[ ! -d "$root" || -L "$root" || ! -r "$root" || ! -x "$root" ]]; then
  printf 'ERROR: каталог недоступен или является ссылкой: %q\n' "$root" >&2
  exit 2
fi
for tool in openssl sha256sum find sort; do
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

check_pair() {
  local directory=$1 key_hash cert_hash file
  printf '\nREQUEST: %q\n' "$directory"
  for file in leaf.key leaf.crt; do
    if [[ ! -f "$directory/$file" || -L "$directory/$file" || ! -r "$directory/$file" ]]; then
      printf 'ERROR: %s отсутствует, недоступен или является ссылкой\n' "$file"
      return 1
    fi
  done
  # SPKI DER normalizes public-key encoding; pipefail rejects an OpenSSL error
  # instead of accepting the SHA256 of empty output. Empty passin prevents prompts.
  if ! key_hash=$(openssl pkey -in "$directory/leaf.key" -passin pass: -pubout -outform DER </dev/null 2>/dev/null | sha256sum); then
    printf 'ERROR: не удалось прочитать leaf.key (формат, шифрование или доступ)\n'
    return 1
  fi
  if ! cert_hash=$(openssl x509 -in "$directory/leaf.crt" -pubkey -noout </dev/null 2>/dev/null |
                   openssl pkey -pubin -outform DER 2>/dev/null | sha256sum); then
    printf 'ERROR: не удалось прочитать открытый ключ leaf.crt\n'
    return 1
  fi
  printf 'KEY_PUBLIC_SHA256:  %s\nCERT_PUBLIC_SHA256: %s\n' "${key_hash%% *}" "${cert_hash%% *}"
  if [[ "$key_hash" == "$cert_hash" ]]; then
    printf 'MATCH: ключ соответствует сертификату\n'
    return 0
  fi
  printf 'MISMATCH: ключ не соответствует сертификату\n'
  return 1
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
