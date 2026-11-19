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

## Démo navigateur

Préparer un compte de démonstration par groupe avec des adresses e-mail
distinctes. Garder une session administrateur séparée pour la préparation.
Utiliser l’origine locale `http://rallly.localhost` ou l’URL affichée par
`python3 scripts/start-tunnel.py`. Pour une démo à distance, tester le lien
depuis un autre appareil et garder le terminal du tunnel ouvert. Transmettre
les identifiants de test séparément et renouveler ceux déjà publiés s’ils
sont encore utilisés. [Démarrage de la démo](../README.md#hébergement-de-linstance-de-test-pour-démo)

| Scénario | Manipulation | Résultat attendu |
| --- | --- | --- |
| SSO autorisé | En navigation privée, ouvrir `/login` sur l’origine active et se connecter avec le compte du groupe `rallly-allowed`. | Retour d’Authentik vers Rallly et session au nom du compte de test. Si nécessaire, terminer le profil au premier accès. |
| SSO refusé | Fermer la session privée et en ouvrir une autre. Repartir de `/login` avec le compte du groupe `rallly-denied`. | Authentik affiche un refus et la connexion Rallly échoue. |
| Inscription externe | Ouvrir une invitation neuve en navigation privée, créer le compte, puis ouvrir `/login` sur la même origine. | Le compte externe est actif et appartient à `rallly-allowed`. Il peut se connecter à Rallly via Authentik. |

Le test de découverte OIDC du lanceur confirme que le tunnel atteint Authentik
avec le bon émetteur. Pour la soutenance, conserver aussi les résultats du
parcours navigateur et des captures sans mots de passe ni jetons.

## Invitation externe

Le blueprint de cette branche crée l’application et les groupes. Préparer le
flux d’inscription séparément dans Authentik.

1. Dans **Flows and Stages → Flows**, créer ou ouvrir le flux `invitation-rallly`.
   Choisir **Enrollment** et exiger une session non authentifiée.
2. Lier les stages dans l’ordre suivant.

   | Ordre | Stage | Réglage de démo |
   | --- | --- | --- |
   | 0 | **Invitation** | Exiger un lien valide. Désactiver la poursuite sans invitation. |
   | 10 | **Prompt** | Demander le nom d’utilisateur, le nom, l’e-mail, le mot de passe et sa confirmation. Utiliser les clés `username`, `name`, `email`, `password` et `password_repeat`. |
   | 20 | **User Write** | Autoriser la création au besoin. Choisir le type **External**, laisser la création de comptes inactifs désactivée et affecter le groupe `rallly-allowed`. |
   | 30 | **User Login** | Ouvrir la session Authentik du nouvel invité. |

3. Dans **Directory → Invitations**, créer une invitation liée à ce flux,
   activer **Single use** et choisir une expiration (par exemple 24 h).
   Copier le lien généré depuis la même origine que le SSO. Pour cette démo,
   partager le lien en privé. L’envoi par e-mail nécessite un SMTP configuré
   dans Authentik.
4. L’invité ouvre le lien en navigation privée et termine le formulaire dans
   le même onglet. Avec la version utilisée dans le projet, un lien à usage
   unique peut être consommé dès l’ouverture du formulaire. Préparer un
   nouveau lien si le parcours est abandonné.
5. Vérifier dans **Directory → Users** que le compte est actif, externe et
   membre de `rallly-allowed`. Toujours dans la session de l’invité, ouvrir
   Rallly sur l’origine active et vérifier le retour SSO. Essayer ensuite le
   lien déjà utilisé dans une nouvelle session privée et vérifier le refus.

Le parcours invitation → compte externe actif → connexion Rallly a été
validé sur l’ancienne stack locale. Rejouer la recette sur la configuration
actuelle et relever les résultats avant la soutenance.

[Créer une invitation dans Authentik](https://docs.goauthentik.io/users-sources/user/invitations/) ·
[Configurer le stage User Write](https://docs.goauthentik.io/add-secure-apps/flows-stages/stages/user_write/)
