FROM python:3.12-slim
RUN groupadd --gid 10001 academy && useradd --uid 10001 --gid academy --no-create-home academy
WORKDIR /app
COPY --chown=academy:academy server.py /app/server.py
COPY --chown=academy:academy maintenance.py /app/maintenance.py
COPY --chown=academy:academy public /app/public
COPY scripts/prepare-assets.py /app/scripts/prepare-assets.py
RUN python3 scripts/prepare-assets.py
RUN mkdir /data && chown academy:academy /data
ENV ACADEMY_DATA_DIR=/data PYTHONUNBUFFERED=1
USER academy
EXPOSE 8000
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python3 -c "import http.client; c=http.client.HTTPConnection('127.0.0.1',8000,timeout=3); c.request('GET','/api/health'); raise SystemExit(0 if c.getresponse().status == 200 else 1)"
CMD ["python3", "server.py", "--host", "0.0.0.0", "--port", "8000"]
