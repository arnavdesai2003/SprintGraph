FROM node:22-bookworm-slim
WORKDIR /tests
COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
RUN npx playwright install --with-deps chromium
COPY . .
ENV CI=1
CMD ["node", "run.cjs"]
