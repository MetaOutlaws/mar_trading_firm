# python:3.11-slim pinned by registry index digest.
# Tag library/python:3.11-slim, last updated 2026-10-22, resolved 2026-10-26.
FROM python:3.11-slim@sha256:b7a9e5f6a93d6d4a31f129bbd4bdee69efccb6ded0fb230d78aafaf37af98377
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TRADING_MODE=paper
COPY docker/cipher-forward-requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY config /app/config
COPY core/__init__.py /app/core/__init__.py
COPY core/strategy /app/core/strategy
COPY docker/cipher-forward-research-init.py /app/research/__init__.py
COPY research/cipher_forward /app/research/cipher_forward
COPY scripts/run_cipher_forward_paper.py /app/scripts/run_cipher_forward_paper.py
COPY docs/cipher-forward /app/docs/cipher-forward
COPY tests/test_cipher_forward.py tests/test_cipher_forward_runtime.py tests/test_cipher_forward_storage.py /app/tests/
COPY CIPHER_RELEASE_SHA /app/CIPHER_RELEASE_SHA
CMD ["python", "scripts/run_cipher_forward_paper.py", "--db", "/state/trial.db", "--context-root", "/context"]
