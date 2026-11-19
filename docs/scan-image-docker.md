# Scan commenté de l'image Docker Rallly

Audit réalisé le **19 novembre 2026**, pour le durcissement demandé au §3.1 du
sujet « Dev avec Docker » et les choix de sécurité à présenter au §6.2.

Le scan détecte **455 occurrences**, correspondant à **210 identifiants d'alerte
distincts**. Il contient **1 critique et 112 élevées**. L'alerte critique nécessite
une distinction entre le paquet source zlib et le composant MiniZip réellement
concerné. Des mises à jour restent nécessaires : ce résultat ne constitue pas une
validation de sécurité pour une mise en production.

## 1. Périmètre et preuves

| Élément | Valeur observée |
| --- | --- |
| Image locale | `infra-rallly_selfhosted:latest` |
| Identifiant de l'image | `sha256:ea15a7e5ca754cef5a946d9fcb6f6c4e89cb21a96a4c61bd3802fd802655e0ce` |
| Construction de l'image | 30 octobre 2026 à 15:17 UTC |
| Plateforme | `linux/arm64` |
| Système détecté | Debian 12.15, famille Bookworm |
| Versions vérifiées dans l'image | Node.js `24.22.2`, npm `11.19.1`, Next.js `16.4.2`, Prisma CLI `7.10.1` |
| Utilisateur de l'image | `nextjs`, UID `100`, GID `101` |
| Outil | Trivy `0.76.2` |
| Base de vulnérabilités | Mise à jour le 19 novembre 2026 à 07:06 UTC ; téléchargée à 10:19 UTC |
| Fin du scan | 19 novembre 2026 à 10:19:24 UTC, soit 11:19:24 à Paris |
| Inventaire analysé | 105 paquets système et 370 entrées de paquets Node.js |

Le scan porte sur l'image utilisée par le conteneur Rallly local, exportée par
`docker image save`. Il ne porte pas sur son volume PostgreSQL, son environnement
d'exécution `.env`, ni les autres images de la stack. Le scanner reçoit l'archive
en lecture seule, sans montage du socket Docker.

Le sous-module du checkout est au commit
`a8ced150729d5da033f5c5fa035d56347e9c71c5`. Aucune attestation reliant
formellement cette image à ce commit n'a été vérifiée : cet identifiant décrit le code présent
pendant l'audit, pas une provenance certifiée du binaire. La CI construit du
`linux/amd64` : son image devra être scannée séparément.

Les preuves sont conservées ensemble :

- [Résultat JSON brut Trivy](security/2026-11-19/rallly-trivy.json).
- [Toutes les occurrences en CSV](security/2026-11-19/vulnerabilities.csv).
- [Totaux calculés](security/2026-11-19/summary.json).
- [Identité de l'image et du scanner](security/2026-11-19/image.json).
- [Manifestes de l'archive exportée](security/2026-11-19/archive-manifest.json).
- [Vérifications dans un conteneur isolé](security/2026-11-19/runtime-checks.json).
- [Date de la base Trivy](security/2026-11-19/db-metadata.json).
- [Empreintes SHA-256 des preuves](security/2026-11-19/checksums.sha256).

Docker identifie ici l'index OCI par `ea15a7…` ; le champ `ImageID` de Trivy
identifie sa configuration sélectionnée par `9ceee4…`. Ces deux identifiants ont
été rapprochés des manifestes de la même archive. Son empreinte complète est
conservée dans `image.json`.

## 2. Résultats principaux

| Gravité | Paquets Debian | Paquets Node.js | Total |
| --- | ---: | ---: | ---: |
| CRITICAL | 1 | 0 | **1** |
| HIGH | 106 | 6 | **112** |
| MEDIUM | 161 | 14 | **175** |
| LOW | 156 | 1 | **157** |
| UNKNOWN | 10 | 0 | **10** |
| **Total** | **434** | **21** | **455** |

Une occurrence est une ligne d'alerte associée à un paquet détecté. Une même CVE
peut apparaître pour plusieurs paquets binaires issus d'un même paquet source :
il ne s'agit donc pas de 455 failles indépendantes. Les 210 identifiants distincts
incluent aussi un avis Debian `DLA`, et ne sont pas exclusivement des CVE.

**26 occurrences, soit 24 identifiants distincts, ont une version corrigée
indiquée par Trivy** : 5 occurrences Debian et les 21 occurrences Node.js. Cela
signifie qu'un correctif est disponible dans les données du scanner, et non qu'il
est déjà installé. Les autres alertes sont conservées, y compris les statuts
`affected`, `fix_deferred` et `will_not_fix`. Aucun filtre de gravité,
`--ignore-unfixed` ou fichier d'exclusion n'a été appliqué.

### Critique : zlib / MiniZip, CVE-2023-45853

Trivy signale `zlib1g` `1:1.2.13.dfsg-1`, gravité CRITICAL, statut `will_not_fix`.
La vulnérabilité concerne la création d'archives par MiniZip. Debian précise que,
dans Bookworm, le code `contrib/minizip` du paquet source zlib n'est pas construit
dans les paquets binaires concernés. Les paquets `minizip`, `libminizip1` et
`python3-pyminizip` sont absents de l'image vérifiée.
[Justification de l'éditeur Debian](https://security-tracker.debian.org/tracker/CVE-2023-45853).

**Décision :** retenir une non-applicabilité au binaire Debian `zlib1g` pour cette
alerte précise. Conserver la ligne critique dans le résultat brut et sa
justification dans ce commentaire ; ne pas masquer globalement la CVE. Cette
conclusion ne couvre pas une copie de MiniZip embarquée par un autre composant.
Elle devra être réexaminée si l'image ou ses dépendances changent. Le statut
`will_not_fix`, à lui seul, ne justifie pas une exemption.

### Correctif disponible : APT, CVE-2026-109518

`apt` et `libapt-pkg6.0` sont détectés en `2.6.1` ; le correctif Bookworm est
`2.6.2`. Cette vulnérabilité concerne les téléchargements de paquets APT dans
certaines conditions de redirection et de nouvelle tentative.
[Avis Debian et version corrigée](https://security-tracker.debian.org/tracker/CVE-2026-109518).

**Décision :** prévoir une reconstruction avec une base et des paquets système
actualisés, puis vérifier la version installée. L'application tourne sans root
et son démarrage ne lance pas APT ; cela réduit l'exposition en fonctionnement,
sans corriger le composant ni supprimer le risque lors de la construction.

### Élevées : dépendances embarquées dans npm

Les six occurrences Node.js HIGH concernent `brace-expansion` `5.0.9` et
`undici` `6.28.0`. Leurs chemins sont sous
`/usr/local/lib/node_modules/npm/node_modules/`, donc dans npm, et non dans la
copie des dépendances de l'application identifiée par le scan.

| Composant | Principales alertes | Correction à prévoir |
| --- | --- | --- |
| `brace-expansion` | CVE-2026-102276 et CVE-2026-102278 : épuisement de pile / déni de service | Version `5.0.12` ou ultérieure dans cette branche pour couvrir aussi l'alerte MEDIUM CVE-2026-102277 |
| `undici` | CVE-2026-109383, CVE-2026-109869, CVE-2026-19534 et CVE-2026-87018 : validation TLS conditionnelle et dénis de service | Version `6.29.1` ou ultérieure compatible, ou version de npm/base Node qui l'embarque |

Les conditions dépendent de l'appelant et des données traitées. Par exemple,
l'alerte TLS sur `undici` concerne un callback de vérification personnalisé perdu
par `Agent` ; ce n'est pas une désactivation générale de toute validation TLS.
[Avis officiel Undici](https://github.com/nodejs/undici/security/advisories/GHSA-2m5v-pch6-74hx).
Les dénis de service de `brace-expansion` supposent le traitement de motifs
malveillants. [Avis officiel brace-expansion](https://github.com/juliangruber/brace-expansion/security/advisories/GHSA-qhr7-859c-m2p7).

**Décision :** actualiser la base Node/npm et vérifier les versions transitives,
plutôt que remplacer manuellement des fichiers internes de npm. Ne pas supprimer
npm sans adapter le démarrage : `docker-start.sh` exécute `npx prisma migrate
deploy`. La simple présence de ces bibliothèques ne démontre pas qu'une requête
Rallly atteint le chemin vulnérable ; aucune preuve d'exploitation n'a été faite.

### Moyennes mais applicatives : Next.js

`next` `16.4.2` est associé à CVE-2026-119351 et CVE-2026-119790, corrigées en
`16.4.5`. Les avis concernent des fuites de données entre paramètres de routes
dans des configurations particulières de cache.
[Premier avis Next.js](https://github.com/vercel/next.js/security/advisories/GHSA-vc7v-qv4w-wrv8),
[second avis Next.js](https://github.com/vercel/next.js/security/advisories/GHSA-mfr8-8qww-v76h).

**Décision :** prioriser aussi cette mise à jour dans le fork, malgré la gravité
MEDIUM, car le framework sert directement l'application. La recherche dans le
checkout trouve `unstable_cache`, mais pas `use cache`, `next/root-params` ou
`cacheComponents`. Cela ne démontre pas les conditions d'exploitation décrites,
et ne remplace pas une mise à jour suivie de tests.

### Nombreuses alertes système sans correctif indiqué

Les bibliothèques Kerberos représentent 92 occurrences, dont 56 HIGH réparties
sur quatre paquets. Plusieurs avis visent les serveurs KDC ou `kadmind`, dont les
binaires aux emplacements standards vérifiés sont absents. De même, des alertes
sur des bibliothèques systemd ne prouvent pas qu'un service `systemd-homed` tourne
dans le conteneur. Ces observations réduisent la portée de certains scénarios,
sans justifier l'exclusion de toutes les alertes d'une famille de paquets.

`curl` et `libcurl4` cumulent 76 occurrences. Le Dockerfile utilise curl pour le
healthcheck HTTP local. Ce contrôle ne sollicite pas les protocoles ou scénarios
de certaines alertes, mais les bibliothèques restent présentes. Remplacer curl
par une sonde Node serait une piste de réduction de surface, à valider avec les
dépendances transitives et le fonctionnement de Prisma.

## 3. Corrections retenues et état réel

**Aucun correctif de dépendance n'a été appliqué pendant cet audit.** Le
sous-module, l'image et les conteneurs applicatifs en service n'ont pas été
modifiés. Le résultat est un état initial avec un plan de traitement, pas un
comparatif avant/après.

| Priorité | Action proposée | Validation attendue |
| --- | --- | --- |
| 1 | Passer Next.js à une version corrigée compatible, au moins `16.4.5`, dans le fork et son lockfile | Build, connexion OIDC/email et tests des fonctionnalités du groupe |
| 1 | Actualiser la base Node/npm et les paquets Debian, notamment APT `2.6.2` | Contrôle des versions embarquées et nouveau scan de l'image reconstruite |
| 2 | Traiter les autres correctifs disponibles : SASL `2.1.28+dfsg-10+deb12u1`, tzdata `2026f-0+deb12u1` et dépendances npm restantes | Vérifier la compatibilité et la disparition des occurrences correspondantes |
| 2 | Étudier la réduction des outils d'exécution, en conservant les migrations Prisma et le healthcheck | Démarrage sur une base vide et existante, conteneur sain |
| 2 | Épingler les bases et outils par version/digest, avec une procédure régulière d'actualisation | Reconstruction traçable et renouvellement des scans |
| 3 | Ajouter un scan et un artefact JSON à la CI après le build `linux/amd64` | Rapport attaché à une exécution sur `main` ; seuil d'échec explicite |

Mesures déjà observées : utilisateur `nextjs` non-root, construction multi-stage,
sortie Next.js standalone, exclusion de `.env*` par `.dockerignore`, pas de port
Rallly ou PostgreSQL publié directement dans le Compose principal. Ces mesures
réduisent certains risques ; elles ne suppriment pas les CVE des composants.
Le Compose actuel n'impose pas `cap_drop: ALL`, `no-new-privileges` ou un système
de fichiers en lecture seule à Rallly : ces protections restent à étudier.

## 4. Limites assumées

- Audit d'une image locale `arm64` déjà construite, sans reconstruction ni
  vérification d'attestation de provenance. Les résultats ne valent pas automatiquement pour
  l'image `amd64` de la CI ou celle déployée sur la VM.
- Scan des vulnérabilités connues des paquets identifiés, à la date de la base.
  L'inventaire ne garantit pas la couverture de chaque binaire, du code compilé
  ou de toutes les dépendances embarquées. Node.js est versionné séparément
  dans les vérifications ; l'absence d'alerte dédiée ne certifie pas sa sécurité.
- Pas de pentest, de preuve d'exploitabilité, de scan des secrets, d'audit de
  licences ou d'audit exhaustif du code et de la configuration. Le choix
  `--scanners vuln` limite volontairement le périmètre.
- Authentik, Traefik, PostgreSQL, Mailpit, l'hôte et le réseau ne sont pas scannés
  par ce rapport. Le SSO ne protège pas automatiquement toutes les routes
  publiques Rallly contre une vulnérabilité applicative.
- Une version corrigée vide signifie « aucun correctif indiqué ici », pas
  « aucun correctif possible ». La gravité Trivy peut provenir de sources
  différentes selon les paquets ; elle sert à orienter l'analyse.
- Les reports de correction sont des limites documentées de cette démo. Ils
  doivent être réévalués avant une exposition durable et à chaque reconstruction.

## 5. Reproduire le scan

Depuis la racine Infra, avec Docker démarré et un accès réseau pour télécharger
Trivy et sa base. Ces commandes exportent l'image locale sans modifier les
conteneurs en service. Utiliser l'identifiant ci-dessus pour viser exactement
l'image auditée, ou le tag pour scanner une nouvelle construction.

```bash
mkdir -p tmp/security-scan .cache/trivy docs/security/rescan
docker image save --output tmp/security-scan/rallly.tar infra-rallly_selfhosted:latest
docker run --rm --cap-drop=ALL --security-opt=no-new-privileges \
  -v "$PWD/tmp/security-scan:/scan:ro" \
  -v "$PWD/docs/security/rescan:/out" \
  -v "$PWD/.cache/trivy:/root/.cache/trivy" \
  aquasec/trivy:0.76.2@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb \
  image --input /scan/rallly.tar --scanners vuln \
  --format json --output /out/rallly-trivy.json --timeout 10m --no-progress
```

Le succès de la commande indique que l'analyse a abouti : le comportement par
défaut ne fait pas échouer le processus lorsqu'une vulnérabilité est trouvée.
Ne pas confondre ce code de sortie avec l'absence d'alertes. La base sera
actualisée : un futur scan peut donc donner des nombres différents. La version
du scanner devra aussi être réévaluée à cette occasion.

Après les corrections, reconstruire explicitement puis refaire le scan :

```bash
docker compose build --pull --no-cache rallly_selfhosted
```

Cette reconstruction n'a pas été exécutée pendant l'audit. Conserver le nouveau
digest, la plateforme, la date de base et les résultats pour comparer les deux
états. Les fichiers d'archive volumineux restent dans `tmp/`, ignoré par Git.

Méthode : [scan d'une archive d'image avec Trivy](https://trivy.dev/docs/latest/target/container_image/)
et [détection des vulnérabilités et choix de gravité](https://trivy.dev/docs/latest/scanner/vulnerability/).

## 6. Commentaire pour la soutenance

« Nous avons scanné l'image locale de notre fork avec Trivy et conservé les
preuves. Les 455 occurrences correspondent à 210 identifiants distincts. La
critique sur zlib est contextualisée par l'avis Debian : le composant MiniZip
concerné n'est pas construit dans ce binaire Bookworm. Nous conservons cette
alerte et sa justification. Les correctifs prioritaires restent Next.js, la base
Node/npm et les paquets système. Le conteneur tourne déjà sans root, mais nous
ne présentons pas ces protections comme des correctifs aux vulnérabilités.
Ce scan est un état initial : une image reconstruite, celle de la CI et celle
de la VM devront être analysées à leur tour. »
