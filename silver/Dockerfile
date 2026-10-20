FROM python:3.12-slim
WORKDIR /app
COPY silver/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY silver/pipeline.py .
ENV PYTHONUNBUFFERED=1
CMD ["python","pipeline.py"]
