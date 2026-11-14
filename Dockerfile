FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /data && python manage.py collectstatic --noinput
ENV DJANGO_DEBUG=0 DATABASE_PATH=/data/31.sqlite3
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && waitress-serve --listen=0.0.0.0:8000 thirtyone.wsgi:application"]
