# Dependencies for the status process. Application source is bind-mounted
# at runtime (docker-compose.status.yml, or deploy/status/docker-compose.sgp1.yml
# on the paper host), so this image does not copy the tree and cannot bake
# a .env or a private key into a layer.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8088

CMD ["python", "scripts/run_status_page.py"]
