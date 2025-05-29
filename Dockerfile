FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y ghostscript libglib2.0-dev libsm6 libxrender1 libxext6 poppler-utils && \
    pip install --no-cache-dir camelot-py[cv] flask pandas openpyxl PyPDF2

WORKDIR /app
COPY . /app

CMD ["python", "app.py"]
