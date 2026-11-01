FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 TZ=Europe/Paris
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot ./bot
COPY config.yaml .
VOLUME ["/app/data"]
HEALTHCHECK --interval=15m CMD python -c "import time,sys; sys.exit(time.time()-int(open('data/heartbeat').read())>1800)"
CMD ["python", "-m", "bot.main"]
