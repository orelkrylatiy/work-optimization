#!/bin/bash
echo "[$(date)] Running startup tasks..."

# echo "Current user: $(whoami)"
# echo "$CONFIG_DIR"

# При рестарте только восстанавливаем сессии и обновляем резюме.
# Live-отклики и ответы запускаются отдельными cron-задачами, чтобы рестарт
# контейнера не создавал неожиданный повторный batch.
/bin/bash /app/scripts/all-profiles.sh refresh
/bin/bash /app/scripts/all-profiles.sh update

echo "[$(date)] Startup tasks finished."
