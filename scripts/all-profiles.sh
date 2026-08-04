#!/usr/bin/env bash
#
# all-profiles.sh — запускает команду параллельно для всех профилей
#
# Использование:
#   ./scripts/all-profiles.sh apply          # dry-run откликов для всех аккаунтов
#   ./scripts/all-profiles.sh reply          # dry-run ответов для всех аккаунтов
#   ./scripts/all-profiles.sh daily          # dry-run workflow для всех аккаунтов
#   ./scripts/all-profiles.sh apply --live   # реальные отклики только с явным --live
#   ./scripts/all-profiles.sh update --live  # реальная публикация резюме
#
# Профили задаются в переменной PROFILES (через пробел) или в файле .profiles
# Пример .profiles (по одному на строку, без комментариев):
#   default
#   account2
#   account3
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Загружаем список профилей
PROFILES_LIST=()
if [[ -f "$PROJECT_ROOT/.profiles" ]]; then
    while IFS= read -r profile; do
        [[ -n "$profile" ]] && PROFILES_LIST+=("$profile")
    done < <(sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$PROJECT_ROOT/.profiles")
elif [[ -n "${PROFILES:-}" ]]; then
    read -ra PROFILES_LIST <<< "$PROFILES"
else
    # Один аккаунт работает без дополнительной настройки.
    PROFILES_LIST=("default")
fi

if [[ ${#PROFILES_LIST[@]} -eq 0 ]]; then
    echo "❌ Список профилей пуст."
    echo "   Проверь файл .profiles или переменную PROFILES"
    exit 1
fi

COMMAND="${1:-daily}"
shift || true
ARGS=("$@")

# Выбор скрипта
case "$COMMAND" in
    apply)  CMD_SCRIPT="$SCRIPT_DIR/apply.sh" ;;
    reply)  CMD_SCRIPT="$SCRIPT_DIR/reply.sh" ;;
    daily)  CMD_SCRIPT="$SCRIPT_DIR/daily.sh" ;;
    boost|update|refresh)  CMD_SCRIPT="" ;;
    *)
        echo "Неизвестная команда: $COMMAND (apply | reply | daily | boost | update | refresh)"
        exit 1
        ;;
esac

# Resume publication changes an HH account and its operation has no native
# dry-run flag.  It must therefore be explicitly enabled even through this
# multi-profile convenience wrapper.  Token refresh is deliberately excluded:
# it only maintains local credentials and does not contact employers.
if [[ "$COMMAND" == "boost" || "$COMMAND" == "update" ]]; then
    LIVE_CONFIRMED=false
    FILTERED_ARGS=()
    for arg in "${ARGS[@]}"; do
        case "$arg" in
            --live) LIVE_CONFIRMED=true ;;
            --dry-run)
                echo "❌ $COMMAND has no preview mode; it was not started. Use --live after reviewing the account."
                exit 1
                ;;
            *) FILTERED_ARGS+=("$arg") ;;
        esac
    done
    if [[ "$LIVE_CONFIRMED" != true ]]; then
        echo "❌ $COMMAND publishes resumes. Re-run with --live to confirm."
        exit 1
    fi
    ARGS=("${FILTERED_ARGS[@]}")
fi

LOG_DIR="${HH_PROFILES_LOG_DIR:-/tmp/hh-profiles}"
mkdir -p "$LOG_DIR"
LOCK_DIR="${HH_PROFILES_LOCK_DIR:-/tmp/hh-profile-locks}"
mkdir -p "$LOCK_DIR"

echo "🚀 Запуск '$COMMAND' для ${#PROFILES_LIST[@]} профилей параллельно"
echo "   Профили: ${PROFILES_LIST[*]}"
echo "   Логи: $LOG_DIR/<profile>-$COMMAND.log"
echo ""

PIDS=()
RUN_PROFILES=()
FAILED=()
for profile in "${PROFILES_LIST[@]}"; do
    if [[ ! "$profile" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]]; then
        echo "❌ Некорректное имя профиля: $profile"
        FAILED+=("$profile")
        continue
    fi
    log="$LOG_DIR/${profile}-${COMMAND}.log"
    lock="$LOCK_DIR/${profile}.lock"
    echo "▶ Запуск профиля: $profile → $log"
    (
        if ! mkdir "$lock" 2>/dev/null; then
            echo "⏭️  Профиль $profile уже обрабатывается; запуск пропущен"
            exit 0
        fi
        trap 'rmdir "$lock" 2>/dev/null || true' EXIT

        if [[ "$COMMAND" == "boost" ]]; then
            hh-applicant-tool --no-auto-auth --profile-id "$profile" boost-resume
        elif [[ "$COMMAND" == "update" ]]; then
            hh-applicant-tool --no-auto-auth --profile-id "$profile" update-resumes
        elif [[ "$COMMAND" == "refresh" ]]; then
            hh-applicant-tool --no-auto-auth --profile-id "$profile" refresh-token
        elif [[ ${#ARGS[@]} -gt 0 ]]; then
            bash "$CMD_SCRIPT" --profile "$profile" "${ARGS[@]}"
        else
            bash "$CMD_SCRIPT" --profile "$profile"
        fi
    ) > "$log" 2>&1 &
    PIDS+=("$!")
    RUN_PROFILES+=("$profile")
done

echo ""
echo "⏳ Ожидание завершения всех профилей..."

for i in "${!PIDS[@]}"; do
    pid="${PIDS[$i]}"
    profile="${RUN_PROFILES[$i]}"
    if wait "$pid"; then
        echo "✅ $profile — завершён"
    else
        echo "❌ $profile — ошибка (см. $LOG_DIR/${profile}-${COMMAND}.log)"
        FAILED+=("$profile")
    fi
done

echo ""
if [[ ${#FAILED[@]} -eq 0 ]]; then
    echo "✅ Все профили обработаны успешно"
else
    echo "⚠️  С ошибками: ${FAILED[*]}"
    exit 1
fi
