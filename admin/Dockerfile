FROM python:3.12.8-slim

WORKDIR /app

RUN pip install --no-cache-dir uv --break-system-packages

COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY . .

RUN useradd --create-home --shell /bin/bash appuser \
     && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
