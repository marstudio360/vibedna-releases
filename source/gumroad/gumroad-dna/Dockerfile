FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Inside a container the web mode (PORT set) must listen on the container's own address; which ports reach it is
# decided by how you run the container. It still needs MCP_HTTP_TOKEN, or it does not start.
ENV MCP_HOST=0.0.0.0
CMD ["python", "server.py"]
