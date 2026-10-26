FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# run as a normal user, and keep the SQLite file in /data
RUN useradd appuser && mkdir /data && chown appuser /data
USER appuser
ENV DB_PATH=/data/queries.sqlite3

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
