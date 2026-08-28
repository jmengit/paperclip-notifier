FROM python:3.12-alpine AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app

RUN addgroup -S -g 10001 notifier && adduser -S -D -u 10001 -G notifier notifier
COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt
COPY pyproject.toml README.md ./
COPY src ./src
COPY config.example.yaml ./config.example.yaml
RUN chown -R notifier:notifier /app

USER 10001:10001
VOLUME ["/data", "/config"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import json,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=3); assert json.load(r)['ok']"
ENTRYPOINT ["python", "-m", "paperclip_notifier.cli"]
CMD ["--config", "/config/config.yaml", "run"]
