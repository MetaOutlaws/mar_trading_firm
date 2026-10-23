FROM python:3.11-slim
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
COPY tests/test_cipher_forward.py tests/test_cipher_forward_runtime.py /app/tests/
COPY CIPHER_RELEASE_SHA /app/CIPHER_RELEASE_SHA
CMD ["python", "scripts/run_cipher_forward_paper.py", "--db", "/state/trial.db", "--context-root", "/context"]
