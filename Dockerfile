FROM python:3.11-slim

WORKDIR /app

# Install required packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY templates/ templates/
COPY master_configuration.yaml .

# Create data directory
RUN mkdir -p /data

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Run the application with Gunicorn
# --preload ensures app is loaded before forking workers (cleanup runs once)
# --worker-class gevent enables WebSocket support via gevent
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--worker-class", "gevent", "--timeout", "120", "--preload", "app:app"]
