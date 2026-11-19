# Architecture

## Vue logique

```text
Navigateur
   |
   v
Traefik (point d'entrée HTTP local :80)
   |------------------------|
   v                        v
Authentik                  Rallly
   |                        |
   v                        v
PostgreSQL Authentik       Base de données Rallly

SMTP de laboratoire : utilisé pour tester les invitations, si nécessaire.
```

Le Compose définit les services `traefik`, `rallly_selfhosted`, `rallly_db`,
`authentik_server`, `authentik_worker` et `authentik_db`. Authentik utilise PostgreSQL
sans Redis dans la version retenue.

## Principes

- Seul Traefik publie le port HTTP de la stack ; les applications et les bases ne publient aucun port.
- Traefik route `/` vers Rallly sur 3000 et `/authentik/` vers Authentik sur 9000, sans condition sur le Host.
- Le réseau `proxy` relie Traefik aux deux applications. `rallly_backend` relie Rallly à sa base ; `authentik_backend` relie le serveur et le worker Authentik à leur base.
- Les deux applications utilisent une seule origine `PUBLIC_BASE_URL` : locale ou HTTPS via un tunnel ngrok.
- `rallly.localhost` reste un alias de développement de Traefik dans Docker ; les domaines publics ne sont pas détournés par un alias local.
- Le routage est déclaré dans `docker/traefik/dynamic/routes.yaml`, monté en lecture seule ; aucun accès au socket Docker n'est requis.
- Des volumes nommés assurent la persistance.
- Les secrets sont injectés depuis l'environnement et ne sont pas intégrés aux images.
- Le déploiement local et la VM utilisent autant que possible le même Compose et les mêmes images ; les écarts sont documentés.
- Authentik est l'IdP OIDC de Rallly : cette intégration doit être réelle et démontrée, pas simulée.
- Deux groupes au minimum doivent avoir des droits distincts ; le processus d'invitation externe doit être documenté et démontré.

## Environnements

### Local
Docker Compose sur macOS, avec `http://rallly.localhost` et `http://rallly.localhost/authentik/`.
Le port HTTP se configure avec `TRAEFIK_HTTP_PORT` dans `.env`. Le TLS n'est pas
configuré dans cette stack locale.

### Tunnel de démonstration

Un tunnel ngrok cible `http://localhost:80`. La même URL HTTPS publique
sert Rallly à la racine et Authentik sous `/authentik/`. Le middleware Traefik fixe
les en-têtes d'origine à `PUBLIC_BASE_URL` pour conserver HTTPS après terminaison
TLS chez ngrok. `scripts/set-public-url.py` synchronise l'environnement,
les services et le callback OIDC quand l'URL publique change.
`scripts/start-tunnel.py` orchestre le tunnel depuis le Mac, découvre l'URL publique
et vérifie Rallly et l'émetteur OIDC avant de présenter les liens. Il garde le tunnel
actif jusqu'à Ctrl+C, puis arrête ngrok et restaure l'origine précédente.

### VM Énov
Déploiement après obtention des accès, configuration du VPN NetBird, accès SSH et création de la VM selon la documentation publique du campus. L'URL et les comptes de démonstration seront ajoutés au README une fois validés.

## Flux OIDC à documenter

1. L'utilisateur ouvre Rallly.
2. Rallly redirige vers Authentik pour l'authentification.
3. Authentik authentifie l'utilisateur et applique les règles d'accès prévues.
4. Authentik renvoie le résultat OIDC à l'URI de redirection configurée.
5. Rallly établit la session applicative.

Les URI, scopes, claims et variables doivent correspondre à la documentation des versions utilisées.
