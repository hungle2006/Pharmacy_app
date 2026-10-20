FROM python:3.12-slim
WORKDIR /app
COPY silver/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY silver/pipeline.py .
COPY silver/sources.json .
ENV PYTHONUNBUFFERED=1 DRY_RUN=true
CMD ["python","pipeline.py"]
