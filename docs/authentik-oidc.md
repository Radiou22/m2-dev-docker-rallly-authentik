# Authentik — OIDC, policies et invitation externe

## Configuration OIDC

Le Compose transmet à Rallly `EMAIL_LOGIN_ENABLED=false`, `OIDC_NAME`,
`OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` et l'URL de découverte construite à partir
de `PUBLIC_BASE_URL` et du préfixe `/authentik/`. Les comptes Rallly sont créés à la
première connexion SSO (`REGISTRATION_ENABLED=true`). La connexion par mail est masquée
et le fork redirige automatiquement vers Authentik.

Le worker charge `docker/authentik/blueprints/rallly.yaml`, qui crée :

- l'application de slug `rallly` et un fournisseur confidentiel en Authorization Code ;
- les scopes `openid`, `profile`, `email`, avec les mappings Authentik par défaut ;
- une clé de signature et les flows d'autorisation et d'invalidation standards ;
- la redirection stricte `${PUBLIC_BASE_URL}/api/auth/callback/oidc`, utilisée par ce fork.

Les secrets sont lus avec les [tags de blueprint Authentik](https://docs.goauthentik.io/customize/blueprints/v1/tags/).
Le worker [charge automatiquement les blueprints locaux](https://docs.goauthentik.io/customize/blueprints/).
Rallly utilise PKCE. Le healthcheck du serveur attend que l'URL de découverte soit
disponible avant de démarrer Rallly.

Valeurs locales par défaut :

| Paramètre | Valeur |
| --- | --- |
| URL Rallly | `http://rallly.localhost` |
| URL Authentik | `http://rallly.localhost/authentik/` |
| Découverte | `http://rallly.localhost/authentik/application/o/rallly/.well-known/openid-configuration` |
| Callback | `http://rallly.localhost/api/auth/callback/oidc` |
| Client ID | `rallly` |

Les deux applications partagent `PUBLIC_BASE_URL`. Traefik accepte tout nom de domaine
et sélectionne Authentik par `PathPrefix(/authentik/)`, avec priorité sur la route `/`
de Rallly. Le chemin est conservé, conformément à `AUTHENTIK_WEB__PATH=/authentik/`.
La route exacte `/authentik` redirige vers `/authentik/`.
Les anciens liens SPA `/flows/` et `/if/` encore générés par cette version
d'Authentik sont redirigés vers leurs équivalents préfixés, avec slash final.

Le nom de développement `rallly.localhost` est un alias Docker de Traefik pour que
Rallly atteigne la même origine que le navigateur. Une URL publique ngrok
est résolue normalement depuis les conteneurs et ne reçoit pas d'alias Docker.

Le middleware `public-origin` transmet le Host, X-Forwarded-Host et X-Forwarded-Proto
issus de l'origine configurée. Ainsi, un tunnel HTTPS aboutissant à Traefik en HTTP
produit toujours des liens et un émetteur OIDC HTTPS. Les ports internes restent
3000 et 9000, sans publication directe.

## Vérification

```bash
docker compose up -d --build --wait
docker compose ps
docker compose logs --tail=100 traefik authentik_worker rallly_selfhosted
```

Définir le mot de passe initial d'`akadmin` depuis l'interface Authentik si nécessaire.
`AUTHENTIK_BOOTSTRAP_EMAIL` ne s'applique qu'à l'initialisation : sur une base existante,
renseigner une adresse mail dans le profil de l'utilisateur Authentik.
Les comptes sans adresse mail ne peuvent pas être créés dans Rallly.

Ouvrir `http://rallly.localhost/login`, se connecter dans Authentik avec un compte
possédant une adresse mail, puis vérifier le retour à une session Rallly authentifiée.

Pour une démo, `python3 scripts/start-tunnel.py` lance le tunnel et détecte son URL.
Il applique cette URL avec `set-public-url.py`, vérifie l'émetteur OIDC public puis
affiche les liens. À l'arrêt, il restaure l'origine précédente.

Pour un tunnel ngrok lancé séparément vers `http://localhost:80`, appliquer son URL
avec le script suivant. Il met à jour `.env`, les conteneurs, l'URL système Authentik
et le callback OIDC, même sur une base déjà initialisée :

```bash
python3 scripts/set-public-url.py https://xxxx.ngrok-free.app
```

Pour revenir au mode local : `python3 scripts/set-public-url.py http://rallly.localhost`.
Après modification du client ID ou du secret, réexécuter ce script avec l'origine active.

Le formulaire de connexion peut être réactivé avec `EMAIL_LOGIN_ENABLED=true` ;
cela demande un SMTP fonctionnel pour l'envoi des codes par mail.

## Groupes et droits d'accès

Le blueprint crée deux groupes persistants, une expression policy `rallly-access`
et son binding à l'application `rallly`. L'application utilise le mode `all` :
une éventuelle autre règle ne peut pas contourner cette restriction.

| Appartenance du compte | Nouvelle connexion SSO à Rallly |
| --- | --- |
| `rallly-allowed` uniquement | Autorisée |
| `rallly-denied` | Refusée |
| Les deux groupes | Refusée, le refus est prioritaire |
| Aucun des deux groupes | Refusée |
| Administrateur Authentik sans groupe de refus | Autorisée |
| Administrateur Authentik dans `rallly-denied` | Refusée |

Les deux groupes ont `is_superuser=false` : l'accès à Rallly ne donne aucun droit
d'administration dans Authentik. La policy ne modifie pas les rôles internes de Rallly.
Les comptes ne sont pas ajoutés automatiquement aux groupes ; leurs membres sont
gérés dans l'interface et conservés lors des réapplications du blueprint.

Pour attribuer l'accès, ouvrir [l'administration Authentik](http://rallly.localhost/authentik/if/admin/),
puis **Directory > Groups**, sélectionner le groupe et modifier ses membres.
La règle s'applique à la connexion OIDC et à la visibilité de l'application dans Authentik.
Les sessions Rallly déjà établies et les sondages publics suivent les règles propres
à Rallly ; changer un groupe ne ferme pas une session Rallly existante.

Après modification du blueprint, le worker le charge automatiquement. Pour appliquer
la configuration et lancer le contrôle des droits immédiatement :

```bash
docker compose up -d --wait
docker compose exec authentik_worker ak apply_blueprint custom/rallly.yaml
docker compose exec -T authentik_worker ak shell < scripts/check-authentik-access.py
```

Le script vérifie le moteur de policies Authentik avec six profils : autorisé,
refusé, membre des deux groupes, sans groupe, administrateur et administrateur refusé.
Il vérifie aussi que réappliquer le blueprint conserve les membres et ne duplique pas le binding.
Il crée des comptes temporaires sans mot de passe utilisable dans une transaction
annulée à la fin, y compris en cas d'échec. Il ne laisse aucun compte de test.

Pour vérifier ensuite le parcours navigateur, utiliser un compte avec une adresse mail,
l'ajouter successivement à chaque groupe, puis relancer la connexion depuis une
session privée sur `http://rallly.localhost/login`. Le groupe autorisé doit permettre
le retour à Rallly ; le groupe refusé doit afficher un refus côté Authentik.

## Invitation externe

- [ ] Configurer le flux d'invitation adapté.
- [ ] Configurer le SMTP de laboratoire si le flux choisi l'exige.
- [ ] Inviter une adresse de test contrôlée par l'équipe.
- [ ] Vérifier la réception, l'activation et l'accès.
- [ ] Documenter les étapes et les limites.

Ne pas considérer ces cases comme réalisées avant d'avoir testé le flux réel.
