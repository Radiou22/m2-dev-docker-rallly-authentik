# Runbook local

La procédure d'installation et les paramètres du `.env` sont décrits dans
[le README](../README.md).

## Vérifications préalables

```bash
docker --version
docker compose version
docker info
```

## Démarrage et diagnostic

```bash
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
docker compose logs -f traefik authentik_server authentik_worker
```

Rallly est accessible sur <http://rallly.localhost> et Authentik sur
<http://authentik.localhost>, via Traefik sur le port 80. Au premier accès,
configurer le compte `akadmin`.
Rallly utilise Authentik pour la connexion ; voir [la configuration OIDC](authentik-oidc.md).

Seul Traefik publie un port. Les accès directs aux applications et aux bases
ne sont plus exposés. Si nécessaire, ajouter
`127.0.0.1 rallly.localhost authentik.localhost` au fichier hosts.

Pour changer le port HTTP public, modifier `TRAEFIK_HTTP_PORT` dans `.env` et ajouter
ce port à `RALLLY_BASE_URL` et `AUTHENTIK_BASE_URL`. Après changement, mettre à jour le callback :

```bash
docker compose up -d --wait
docker compose exec authentik_worker ak apply_blueprint custom/rallly.yaml
```

## Arrêt

`docker compose down` arrête les services en conservant les volumes PostgreSQL
et les fichiers Authentik. L'option `--volumes` supprime toutes ces données.
