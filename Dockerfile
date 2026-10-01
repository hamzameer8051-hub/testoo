FROM python:3.11-slim
WORKDIR /app
COPY poc.html server.py ./
CMD ["python3", "server.py"]
