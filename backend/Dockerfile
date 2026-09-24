FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY ml/ ml/
COPY data/ data/
COPY scripts/ scripts/
RUN useradd -m ascension && chown -R ascension:ascension /app
USER ascension
EXPOSE 8000
CMD ["python","scripts/serve.py"]
