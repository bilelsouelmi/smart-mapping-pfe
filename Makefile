.PHONY: help dev up down logs clean

help:
	@echo "Commandes disponibles:"
	@echo "  make dev    - Demarrer en mode developpement"
	@echo "  make up     - Demarrer en arriere-plan"
	@echo "  make down   - Arreter tout"
	@echo "  make logs   - Voir les logs"
	@echo "  make clean  - Tout nettoyer"

dev:
	docker-compose up

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	docker system prune -f
