FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY telephony/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home app && mkdir /data && chown app:app /data
COPY telephony ./telephony
USER app
CMD ["uvicorn", "telephony.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
