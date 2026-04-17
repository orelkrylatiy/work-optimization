# Stage 1: Base с системными зависимостями
FROM python:3.13-slim as base

RUN apt-get update && apt-get install -y --no-install-recommends \
  gcc \
  libc6-dev \
  procps \
  cron \
  dos2unix \
  tzdata \
  curl \
  ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Настройка пользователя
ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID docker && \
  useradd -u $UID -g docker -m -s /bin/bash docker

WORKDIR /app

# Stage 2: Build - установка зависимостей, скачивание браузера
FROM base as builder

COPY pyproject.toml poetry.lock* README.md /app/
COPY admin/requirements.txt /app/admin/requirements.txt

# Установка playwright и браузера в этот слой
RUN pip install --no-cache-dir --user playwright && \
  apt-get update && apt-get install -y --no-install-recommends \
  libnss3 libxss1 && \
  su docker -c "python -m playwright install chromium" && \
  apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false && \
  rm -rf /var/lib/apt/lists/*

# Установка зависимостей приложения
COPY src /app/src
RUN pip install --no-cache-dir --user -e '.[playwright,pillow]' && \
  pip install --no-cache-dir --user -r /app/admin/requirements.txt

# Stage 3: Runtime - минимальный финальный образ
FROM base as runtime

# Копируем только необходимое из builder
COPY --from=builder /root/.local /home/docker/.local
COPY --from=builder /app/src /app/src
COPY --from=builder /app/pyproject.toml /app/

# Копируем конфиги и скрипты
COPY admin /app/admin
COPY config /app/config
COPY crontab /app/crontab
COPY container-entrypoint.sh /app/container-entrypoint.sh
COPY startup.sh /app/startup.sh

# Настройка PATH
ENV PATH="/home/docker/.local/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Настройка крона
RUN dos2unix /app/crontab && \
  dos2unix /app/container-entrypoint.sh && \
  chmod +x /app/startup.sh && \
  chmod +x /app/container-entrypoint.sh && \
  chmod 0644 /app/crontab && \
  crontab -u docker /app/crontab && \
  chown -R docker:docker /app

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD printenv | grep -E 'CONFIG_DIR|HH_PROFILE_ID|LOG_LEVEL' >> /etc/environment && \
  exec /app/container-entrypoint.sh
