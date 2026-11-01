# Level 3 extractor: deterministic tools only (step 1 of the technology ladder).
# Runs on the VPS in archive_net; reads artifacts decrypted from the cold store into a RAM-only /work.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      poppler-utils tesseract-ocr tesseract-ocr-rus tesseract-ocr-pol libimage-exiftool-perl p7zip-full \
      libreoffice-writer-nogui libreoffice-calc-nogui libreoffice-impress-nogui \
      curl unzip ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Siegfried (format identification against PRONOM) with its signature data
ARG SF=1-11-9
RUN curl -sSL -o /tmp/sf.zip https://github.com/richardlehane/siegfried/releases/download/v1.11.9/siegfried_${SF}_linux64_static.zip \
 && curl -sSL -o /tmp/data.zip https://github.com/richardlehane/siegfried/releases/download/v1.11.9/data_${SF}.zip \
 && unzip -oq /tmp/sf.zip -d /usr/local/bin && unzip -oq /tmp/data.zip -d /opt && rm /tmp/*.zip

COPY --from=rclone/rclone:1.68.2 /usr/local/bin/rclone /usr/local/bin/rclone

RUN pip install --no-cache-dir extract-msg==0.55.0 "psycopg[binary]==3.2.10" charset-normalizer==3.4.3

COPY extract.py /app/extract.py
WORKDIR /work
ENTRYPOINT ["python", "/app/extract.py"]
