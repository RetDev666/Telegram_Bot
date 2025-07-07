FROM python:3.11-slim

WORKDIR /app

# Встановити Tesseract OCR для DigitalOcean
RUN apt-get update && apt-get install -y \
    tesseract-ocr tesseract-ocr-ukr tesseract-ocr-eng \
    libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV TESSERACT_PATH=/usr/bin/tesseract
ENV PORT=8000

EXPOSE 8000

CMD ["python", "run.py"] 