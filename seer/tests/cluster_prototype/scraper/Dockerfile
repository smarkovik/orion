FROM python:3.12-slim
ARG HTTPS_PROXY
ARG HTTP_PROXY
ARG NO_PROXY
COPY certs/ /tmp/certs/
RUN cat /tmp/certs/*.crt >> /etc/ssl/certs/ca-certificates.crt 2>/dev/null || true
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY scraper/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY scraper/ .
CMD ["python", "scrape.py"]
