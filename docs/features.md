# Fonctionnalités Rallly

Le dépôt d’infrastructure intègre les quatre changements ci-dessous via le
sous-module `rallly`. Les fonctionnalités du catalogue sont le quota par créneau
(n° 3) et le blocage des votes sur les créneaux passés (n° 5).

## Quota par créneau (catalogue n° 3)

Sur un sondage ouvert, l’organisateur peut fixer une limite de votes **Oui**.
La limite s’applique séparément à chaque créneau. Seuls les **Oui** occupent
une place.

1. Créer un sondage avec deux créneaux futurs. Sur sa page de gestion, ouvrir
   **Slot capacity**, saisir `1` et enregistrer.
2. Enregistrer un premier **Oui** sur le premier créneau.
3. Depuis une autre session, essayer un second **Oui** sur ce créneau. Rallly
   refuse l’enregistrement et affiche que le créneau est plein.
4. Choisir le second créneau, encore disponible, puis enregistrer la réponse.

[Capture du refus](screenshots/quota.png) · [Code et tests dans la PR #1](https://github.com/Radiou22/rallly/pull/1)

## Blocage des votes sur les créneaux passés (catalogue n° 5)

Un créneau horaire devient non modifiable à son heure de début. Une date sans
horaire reste disponible jusqu’à la fin de la journée dans le fuseau du sondage
(UTC par défaut). Les votes déjà enregistrés sur les options passées sont
conservés. Les options futures restent ouvertes au vote.

1. Ouvrir un sondage avec un créneau passé et un autre futur.
2. Vérifier que le premier est désactivé et qu’une réponse sur le second
   s’enregistre.
3. Si un vote a été enregistré avant le début du premier créneau, modifier la
   réponse sur le créneau futur et vérifier que le vote passé reste affiché.

[Capture d’un créneau désactivé](screenshots/blocage-votes.png) · [Code et tests dans la PR #2](https://github.com/Radiou22/rallly/pull/2)

## Fonctionnalité libre — afficher les noms longs au survol

Dans le tableau des votes, un nom trop long est tronqué. Quand le pointeur
survole ce nom, Rallly l’affiche en entier et masque temporairement les
commandes de la ligne pour éviter leur chevauchement. Pour la démo, enregistrer
une réponse avec un nom long, puis survoler ce nom dans le tableau sur ordinateur.

[Capture du nom complet](screenshots/overlap.png) · [Modification du fork](https://github.com/Radiou22/rallly/commit/a8ced150729d5da033f5c5fa035d56347e9c71c5)

## Amélioration complémentaire — centrer le code de vérification e-mail

Les cases de saisie du code reçu par e-mail sont maintenant centrées sur
l’écran de vérification Rallly. Pour le démontrer, utiliser une instance de
test avec `EMAIL_LOGIN_ENABLED=true` et un SMTP fonctionnel. Ouvrir la connexion
par e-mail et demander un code. La stack de démo Authentik désactive la connexion
par e-mail par défaut.

[Modification du fork](https://github.com/Radiou22/rallly/commit/9bd72a86ca742ba7544091989b1d593353259ca5)
