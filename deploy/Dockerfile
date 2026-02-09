FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE $PORT

CMD ["uvicorn", "api.revenue_api:route_request", "--host", "0.0.0.0", "--port", "$PORT"]
