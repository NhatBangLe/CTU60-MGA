FROM oven/bun:latest AS builder

WORKDIR /app
COPY . .
RUN bun install
RUN bun run build

FROM oven/bun:latest AS runner

WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY ./package.json .
RUN bun install --production

EXPOSE 3000
CMD [ "bun", "start:prod" ]