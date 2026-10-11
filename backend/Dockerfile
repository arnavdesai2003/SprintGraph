FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN if [ -f requirements.lock ]; then pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps '.[dev]'; else pip install --no-cache-dir '.[dev]'; fi
RUN pip check
RUN useradd --create-home sprintgraph && chown -R sprintgraph /app
USER sprintgraph
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
