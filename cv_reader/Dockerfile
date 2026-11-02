# CV reading pass: a model lists the roles in each CV. Reads only the database, never the cold store.
FROM python:3.12-slim

RUN pip install --no-cache-dir anthropic==2.3.0 "psycopg[binary]==3.2.10"

COPY read_cv.py /app/
ENTRYPOINT ["python", "/app/read_cv.py"]
