FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
# --trusted-host: necessário em redes corporativas com inspeção de TLS (proxy
# corporativo), cujo certificado raiz não está na cadeia de confiança da imagem base.
RUN pip install --no-cache-dir \
    --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
