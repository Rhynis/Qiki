#!/usr/bin/env bash
set -euo pipefail

PRIVATE_KEY_RE="BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY"

print_usage() {
  cat <<'USAGE'
Usage: scripts/secret-scan.sh [--tracked|--staged]

  --tracked  Scan tracked repository files and .env.example placeholders.
  --staged   Scan staged files for private keys before commit.
USAGE
}

is_placeholder_value() {
  local value="$1"

  value="${value%%#*}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"

  [[ -z "$value" ]] && return 0
  [[ "$value" =~ ^(<.*>|\$\{.*\})$ ]] && return 0
  [[ "$value" =~ ^(your|example|sample|dummy|test|placeholder|changeme|change_me|change-me|replace-me|xxx|todo)[-_A-Za-z0-9]*$ ]] && return 0
  [[ "$value" =~ ^(your|example|sample|dummy|test|placeholder|changeme|change_me|change-me|replace-me|xxx|todo)[-_] ]] && return 0

  return 1
}

scan_tracked_private_keys() {
  if git grep -nE "$PRIVATE_KEY_RE" -- .; then
    echo "::error::Private key found in tracked files"
    return 1
  fi
}

scan_staged_private_keys() {
  local files=()
  local file
  local file_count=0

  while IFS= read -r -d '' file; do
    files+=("$file")
    file_count=$((file_count + 1))
  done < <(git diff --cached --name-only -z --diff-filter=ACMR)

  [[ "$file_count" -eq 0 ]] && return 0

  if git grep --cached -nE "$PRIVATE_KEY_RE" -- "${files[@]}"; then
    echo "Commit blocked: private key found in staged files." >&2
    echo "Remove the secret, rotate the exposed key, then stage the sanitized file." >&2
    return 1
  fi
}

scan_env_examples() {
  local failed=0
  local line line_no key value file

  while IFS= read -r -d '' file; do
    if grep -nE "BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|service_account" "$file"; then
      echo "::error file=$file::Secret material found in .env.example"
      failed=1
    fi

    line_no=0
    while IFS= read -r line || [[ -n "$line" ]]; do
      line_no=$((line_no + 1))
      [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue

      if [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=[[:space:]]*(.*)$ ]]; then
        key="${BASH_REMATCH[2]}"
        value="${BASH_REMATCH[3]}"

        if [[ "$key" == "GOOGLE_APPLICATION_CREDENTIALS_JSON" || "$key" =~ (_KEY|_SECRET)$ ]]; then
          if ! is_placeholder_value "$value"; then
            echo "::error file=$file,line=$line_no::Secret-like value found for $key in .env.example"
            failed=1
          fi
        fi
      fi
    done < "$file"
  done < <(git ls-files -z -- '*env.example')

  return "$failed"
}

mode="${1:---tracked}"
case "$mode" in
  --tracked)
    scan_tracked_private_keys
    scan_env_examples
    ;;
  --staged)
    scan_staged_private_keys
    ;;
  -h|--help)
    print_usage
    ;;
  *)
    print_usage >&2
    exit 2
    ;;
esac
