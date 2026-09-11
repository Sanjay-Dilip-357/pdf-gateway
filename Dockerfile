FROM python:3.11-slim

# Install LibreOffice + fontconfig utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy custom Microsoft fonts and build system font cache
RUN mkdir -p /usr/share/fonts/truetype/custom
COPY fonts/ /usr/share/fonts/truetype/custom/
RUN chmod 644 /usr/share/fonts/truetype/custom/* && fc-cache -f -v

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

EXPOSE 10000
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "120", "app:app"]
