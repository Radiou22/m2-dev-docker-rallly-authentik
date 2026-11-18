# Déploiement de Rallly avec Authentik

La stack construit notre fork depuis le sous-module `rallly` et lance Authentik
(serveur et worker) avec une base PostgreSQL dédiée. Traefik est le point d'entrée
HTTP commun aux deux applications. Les données sont conservées dans des volumes Docker.

Avec Docker et Docker Compose 2.24 ou supérieur :

```shell
git submodule update --init --recursive
# Uniquement si .env n'existe pas encore :
cp .env.example .env
chmod 600 .env
```

Renseigner les quatre secrets vides du `.env` avec les résultats de ces commandes
(une commande par variable, conserver ces secrets après initialisation) :

```shell
openssl rand -hex 32  # RALLLY_SECRET
openssl rand -hex 32  # AUTHENTIK_DB_PASSWORD
openssl rand -hex 60  # AUTHENTIK_SECRET_KEY
openssl rand -hex 32  # OIDC_CLIENT_SECRET
```

Le `.env` local est déjà renseigné avec des secrets générés. Le mot de passe de la
base Rallly reste `postgres` pour conserver la compatibilité avec un volume existant ;
pour une nouvelle installation, le remplacer par une valeur hexadécimale.
Modifier un mot de passe dans `.env` ne change pas celui d'une base déjà initialisée.

```shell
docker compose config --quiet
docker compose up -d --build
```

- Rallly : <http://rallly.localhost>
- Authentik : <http://authentik.localhost>

Seul Traefik publie un port sur la machine (`TRAEFIK_HTTP_PORT=80` par défaut).
Les applications et PostgreSQL sont accessibles sur leurs réseaux Docker respectifs.
Les anciens accès directs sur les ports 3000, 9000, 9443 et 5450 sont supprimés.
La configuration locale utilise HTTP ; aucun certificat TLS n'est configuré.

Les routes sont définies dans `docker/traefik/dynamic/routes.yaml` avec le
[file provider de Traefik](https://doc.traefik.io/traefik/reference/routing-configuration/other-providers/file/).
Traefik lit `RALLLY_HOST` et `AUTHENTIK_HOST` depuis `.env` et n'a pas besoin du socket Docker.
`RALLLY_BASE_URL` et `AUTHENTIK_BASE_URL` reprennent ces noms dans `.env`.
Pour utiliser le port 8088, définir `TRAEFIK_HTTP_PORT=8088` et ajouter `:8088`
aux deux URL publiques, puis ouvrir `http://rallly.localhost:8088`.

Au premier accès à Authentik, définir le mot de passe du compte `akadmin`.
Son adresse mail initiale est définie par `AUTHENTIK_BOOTSTRAP_EMAIL` ; chaque
utilisateur doit avoir une adresse mail renseignée pour se connecter à Rallly.

Compte administrateur de l'environnement local :

- Adresse mail : `akadmin@test.fr`
- Mot de passe : `a`

Les domaines, le port HTTP public, les versions et la base Authentik se règlent dans `.env`.
Cette version utilise PostgreSQL sans Redis. Le worker n'a pas accès au socket Docker ;
les éventuels outposts externes doivent être déployés manuellement.

La connexion par mail de Rallly est désactivée (`EMAIL_LOGIN_ENABLED=false`).
Rallly redirige automatiquement vers Authentik. Le blueprint monté dans le worker
crée l'application OIDC `rallly`, son fournisseur et les scopes `openid profile email`.
Le client ID et le secret sont partagés via `.env` ; aucune saisie manuelle de ces
valeurs dans Authentik n'est nécessaire. Rallly attend que le fournisseur soit prêt.

Les noms `rallly.localhost` et `authentik.localhost` pointent vers la boucle locale
dans les navigateurs compatibles avec `.localhost`, et vers Traefik sur le réseau Docker.
Si le navigateur ne les résout pas, ajouter
`127.0.0.1 rallly.localhost authentik.localhost` dans le fichier hosts de la machine.
Utiliser les mêmes adresses publiques dans le navigateur et pour OIDC.

Après une migration depuis les anciens ports ou une modification des URL, réappliquer
le blueprint pour mettre à jour le callback du fournisseur existant :

```shell
docker compose up -d --wait
docker compose exec authentik_worker ak apply_blueprint custom/rallly.yaml
```

Voir [la configuration et la vérification OIDC](docs/authentik-oidc.md).
Les paramètres SMTP facultatifs de Rallly peuvent rester dans `rallly/apps/web/.env`.

```shell
docker compose ps
docker compose logs -f traefik authentik_server authentik_worker
docker compose down  # conserve les données
```

Le workflow `.github/workflows/ci.yml` vérifie le dépôt puis construit l'image Docker
du fork sur les push et les pull requests vers `main`. Il peut aussi être lancé
manuellement depuis GitHub Actions. Le checkout initialise récursivement les
sous-modules à la révision enregistrée dans Infra.

Le build utilise `rallly/apps/web/Dockerfile`, le contexte `rallly` et
`SELF_HOSTED=true`, pour une image Linux amd64 nommée `rallly-fork:<commit Infra>`.
Les couches sont mises en cache dans GitHub Actions. L'image est chargée dans le
runner pour la durée du job ; elle n'est pas publiée dans un registre.
