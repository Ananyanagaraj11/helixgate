FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY dashboard ./dashboard
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONPATH=src
EXPOSE 8080
CMD ["sh", "-c", "uvicorn helixgate.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
