FROM public.ecr.aws/lambda/python:3.12
ARG HTTPS_PROXY
ARG HTTP_PROXY
ARG NO_PROXY
COPY certs/ /tmp/certs/
RUN cat /tmp/certs/*.crt >> /etc/pki/tls/certs/ca-bundle.crt 2>/dev/null || true
ENV SSL_CERT_FILE=/etc/pki/tls/certs/ca-bundle.crt REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt PIP_CERT=/etc/pki/tls/certs/ca-bundle.crt PYTHONUNBUFFERED=1
COPY lambdas/ingest/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY lambdas/common/seer_common/ ${LAMBDA_TASK_ROOT}/seer_common/
COPY sources.yaml ${LAMBDA_TASK_ROOT}/sources.yaml
COPY lambdas/ingest/handler.py ${LAMBDA_TASK_ROOT}/
CMD ["handler.handler"]
