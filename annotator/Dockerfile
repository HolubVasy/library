# Annotation pass: a model writes what each document is about. Reads only the database, never the cold store.
FROM python:3.12-slim

RUN pip install --no-cache-dir anthropic==2.3.0 "psycopg[binary]==3.2.10"

COPY annotate.py /app/
ENTRYPOINT ["python", "/app/annotate.py"]
