FROM public.ecr.aws/lambda/python:3.12
ARG HTTPS_PROXY
ARG HTTP_PROXY
ARG NO_PROXY
COPY certs/ /tmp/certs/
RUN cat /tmp/certs/*.crt >> /etc/pki/tls/certs/ca-bundle.crt 2>/dev/null || true
ENV SSL_CERT_FILE=/etc/pki/tls/certs/ca-bundle.crt REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt PIP_CERT=/etc/pki/tls/certs/ca-bundle.crt PYTHONUNBUFFERED=1
COPY lambdas/stories/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
# Bake the model; the HF cache is throwaway.
RUN HF_HOME=/tmp/hf-build python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base', device='cpu').save('/opt/model/e5-base')" \
    && rm -rf /tmp/hf-build /root/.cache
ENV MODEL_PATH=/opt/model/e5-base HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/tmp/hf TORCH_HOME=/tmp/torch
COPY lambdas/common/seer_common/ ${LAMBDA_TASK_ROOT}/seer_common/
COPY clusterer/cluster.py categories.yaml ${LAMBDA_TASK_ROOT}/
COPY lambdas/stories/handler.py ${LAMBDA_TASK_ROOT}/
CMD ["handler.handler"]
