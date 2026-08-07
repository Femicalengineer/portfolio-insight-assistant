# Dockerfile
FROM python:3.12-slim

WORKDIR /code

COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY questrade_mcp_server.py /code/questrade_mcp_server.py

CMD ["python", "questrade_mcp_server.py"]