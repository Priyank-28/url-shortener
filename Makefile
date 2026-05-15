.PHONY: up down logs shell-api shell-db ps build

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api

ps:
	docker compose ps

build:
	docker compose build

shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec db psql -U urluser -d urldb