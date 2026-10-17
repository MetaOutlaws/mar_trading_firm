FROM python:3.12-slim
RUN pip install --no-cache-dir numpy==2.3.5 pandas==2.2.3 pydantic-settings==2.16.0
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TRADING_MODE=paper
WORKDIR /research
ENTRYPOINT ["python", "-I"]
