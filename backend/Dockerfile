FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 sipi
COPY --chown=sipi:sipi . .
RUN mkdir -p /app/staticfiles && chown sipi:sipi /app /app/staticfiles
USER sipi
EXPOSE 8000
CMD ["sh", "entrypoint.sh"]
