FROM python:3.12-slim
WORKDIR /app
COPY seller/ seller/
COPY data/ data/
COPY agent_card.json server.py ./
RUN pip install --no-cache-dir requests
EXPOSE 8080
USER nobody
CMD ["python", "server.py", "--port", "8080"]
