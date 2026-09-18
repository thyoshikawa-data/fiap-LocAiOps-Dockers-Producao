FROM apache/airflow:2.9.3-python3.11

COPY requirements.txt /requirements.txt
# --trusted-host: necessário em redes corporativas com inspeção de TLS (proxy
# corporativo), cujo certificado raiz não está na cadeia de confiança da imagem base.
RUN pip install --no-cache-dir \
    --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    -r /requirements.txt
