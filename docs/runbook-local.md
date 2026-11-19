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
<http://rallly.localhost/authentik/>, via Traefik sur le port 80. Au premier accès,
configurer `akadmin` sur <http://rallly.localhost/authentik/if/flow/initial-setup/>.
Rallly utilise Authentik pour la connexion ; voir [la configuration OIDC](authentik-oidc.md).

Dans le mode habituel, seul Traefik publie un port. Les accès directs aux applications et aux bases
ne sont plus exposés. Si nécessaire, ajouter
`127.0.0.1 rallly.localhost` au fichier hosts.

Pour changer le port HTTP local, modifier `TRAEFIK_HTTP_PORT` dans `.env`, puis
appliquer l'origine avec ce port. Par exemple, pour le port 8088 :

```bash
python3 scripts/set-public-url.py http://rallly.localhost:8088
```

## Démo avec un tunnel public

Avec Python 3.10 ou supérieur, ngrok installé et son authtoken configuré :

```bash
python3 scripts/start-tunnel.py
```

Le script lance un seul tunnel vers le port Traefik configuré, détecte son URL,
met à jour `.env`, synchronise Authentik et affiche les liens après vérification.
L'agent ngrok utilise TLS sur 443/TCP. Le script récupère l'URL dans l'événement
JSON de démarrage du tunnel, puis vérifie les applications et l'émetteur OIDC.
Rallly est à la racine de cette URL, Authentik sous `/authentik/`.
**Ctrl+C** arrête le tunnel et restaure l'origine précédente.

Utiliser `--verbose` pour afficher les logs ngrok et `--timeout 120` pour augmenter
le délai d'attente. Pour un tunnel lancé séparément, appliquer son URL avec
`python3 scripts/set-public-url.py https://xxxx.ngrok-free.app`.
Le retour local manuel reste disponible avec
`python3 scripts/set-public-url.py http://rallly.localhost`.

Si ngrok s'arrête avant de fournir une URL, consulter `--verbose`, lancer
`ngrok config check` et vérifier que l'authtoken est configuré avec
`ngrok config add-authtoken TON_TOKEN`. Les vérifications HTTP du script utilisent
l'en-tête ngrok prévu pour les clients automatisés.

## Vérification email avec Mailpit

```bash
python3 scripts/start-tunnel.py --email-login
```

L'option applique `docker-compose.email.yaml` : formulaire email activé dans
Rallly, SMTP interne `mailpit:1025`, boîte de réception sur
<http://localhost:8025>. Saisir une adresse de test dans Rallly puis récupérer
le code dans Mailpit. Aucun email ne part vers une boîte réelle. L'interface
Mailpit reste accessible uniquement depuis l'hôte, en dehors du tunnel.
Authentik reste disponible, mais une connexion email ne consulte pas ses groupes.

Pour tester uniquement en local :

```bash
python3 scripts/set-public-url.py http://rallly.localhost --email-login
```

À l'arrêt du lanceur, le mode défini dans `.env` est rétabli. Pour revenir
manuellement au mode habituel et supprimer la boîte de test :

```bash
python3 scripts/set-public-url.py http://rallly.localhost
docker compose -f docker-compose.yaml -f docker-compose.email.yaml rm -sf mailpit
```

Mailpit conserve les messages tant que son conteneur existe ; la suppression
du conteneur efface cette boîte de test.

## Arrêt

`docker compose down` arrête les services en conservant les volumes PostgreSQL
et les fichiers Authentik. L'option `--volumes` supprime toutes ces données.
Si Mailpit a été lancé, utiliser
`docker compose -f docker-compose.yaml -f docker-compose.email.yaml down`
pour arrêter également ce service.
