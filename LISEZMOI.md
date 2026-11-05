# sprezzature-publish

[🇫🇷](https://github.com/warith-harchaoui/sprezzature-publish/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/sprezzature-publish/blob/main/README.md)

Un dossier de Markdown devient un site que quelqu'un peut trouver.

Pointez-le sur un `README.md` et un dossier `docs/` : il en sort des pages,
les balises qui les rendent partageables, un jeu de favicons et d'icônes
d'application à partir d'un seul logo, les index que les robots et les
modèles de langue vont chercher — `robots.txt`, `sitemap.xml`, `llms.txt`, un
flux Atom, `humans.txt` — et, si on le demande, une narration audio avec un
suivi qui surligne la phrase en train d'être lue.

Il est taillé pour un site qu'on tient dans sa tête : un README, quelques
pages de documentation, un blog. Pour cent pages versionnées, prenez MkDocs
Material, Hugo ou Astro ; celui-ci ne les concurrence pas et le dit.

---

## Comment ça marche

![Schéma de flux. En haut, un README, un dossier de documentation, un journal des versions et un logo alimentent deux voies. La voie de gauche fabrique : elle rend les pages, transforme le logo en jeu d'icônes complet, écrit les index que cherchent les robots et les modèles de langue, et narre le texte avec une voix locale liée à la page. La voie de droite contrôle : elle relit le Markdown avant tout rendu, relit le site construit ou une adresse en ligne, et cite une spécification pour chaque règle. Les deux se rejoignent en un seul résultat, un site où un moteur de recherche, un modèle de langue et un lecteur trouvent chacun leur chemin.](https://raw.githubusercontent.com/warith-harchaoui/sprezzature-publish/main/assets/comment-ca-marche.svg)

## Ce qu'il y a dedans

| | |
|---|---|
| `sprezzature-publish-lint` | **audit** — lire le Markdown avant que quoi que ce soit ne le rende. click et la bibliothèque standard, rien d'autre, quelques millisecondes, taillé pour un crochet de pré-commit. `--fix` répare ce qui a une réparation sûre. |
| `sprezzature-publish-audit` | **audit** — lire le site *après* qu'il existe : balises du head, Open Graph, liens d'icônes, `robots.txt`, `sitemap.xml`, `llms.txt`. Prend un dossier, une page ou une URL vivante — aucune source Markdown requise. `--fix` réécrit ce qui se dérive, jamais ce qui s'invente. |
| `sprezzature-publish-cta` | **d'abord** — trouver les appels à l'action que le site offre déjà, demander lesquels il sert, écrire `ctas.yaml`, et vérifier chaque page contre eux. Lit HTML, PHP, Markdown, JSON et YAML. |
| `sprezzature-publish-faq` | **make** — construire la FAQ qui manque au site à partir de ses propres pages : questions classées par le CTA déclaré, réponses ancrées dans les mots du site, questions auxquelles il ne sait pas encore répondre. **audit** — le balisage `FAQPage` contre la FAQ visible, `--fix` le réécrit. |
| `sprezzature-publish-findable` | **audit** — un seul rapport SEO + GEO + AEO, pages argent d'abord, chaque constat étiqueté avec tous les buts qu'il sert. `--fix` applique les réparations déterministes. |
| `sprezzature-publish-html` | Markdown → pages HTML autonomes, diagrammes Mermaid rendus. |
| `sprezzature-publish-icons` | un logo → favicon, icônes d'application, icônes PWA, et le fragment de `<head>` qui les référence. |
| `sprezzature-publish-indexes` | `robots.txt`, `sitemap.xml`, `llms.txt`, `llms-full.txt`, Atom, `humans.txt`. |
| `sprezzature-publish-meta` | Open Graph, Twitter Card et Schema.org JSON-LD, rédigés par un modèle local. |
| `sprezzature-publish-plain` | réécrire la prose à un niveau de lecture visé, en gardant les termes que vous nommez. |
| `sprezzature-publish-changelog` | le `CHANGELOG.md` de chaque dépôt voisin sous `--repos-root` devient un seul flux Atom et RSS, une version datée par entrée. |
| `sprezzature-publish-narrate` | narrer un billet avec une voix locale, et écrire la piste temporisée à côté de l'audio. |
| `sprezzature-publish-readalong` | lier cette narration à la page, pour que la phrase prononcée soit surlignée. |

Une seule porte d'entrée sur les treize, en click, sous deux noms :
`make-site <outil>` et `sprezzature-publish <outil>` résolvent vers le même
appelable, donc ils ne peuvent pas diverger. Le jumeau argparse a été retiré
le 2026-10-25, et le 2026-11-04 les commandes par outil et le serveur MCP ont
suivi : toutes les commandes d'ici sont en click.

## Installation

```sh
pip install sprezzature-publish
```

Une ligne, et c'est tout : le lint, le rendu, le jeu d'icônes, les outils à
modèle local, la narration, la surface HTTP et le serveur MCP.

Jusqu'au 2026-11-01 ce bloc faisait six lignes et il fallait choisir — la base
était une seule dépendance, donc `pip install sprezzature-publish` donnait un
lint et rien d'autre, et savoir quel extra on voulait était un prérequis pour
que le paquet serve. Les extras sont partis ; `[dev]` est l'outillage de test
et n'en est pas un.

Demande **Python 3.10–3.13** : `sprezzature-audio`, désormais en base,
déclare `<3.14` à la version que nomme le manifeste.

Que le lint n'ait besoin **que de click et de la bibliothèque standard** est
délibéré, et c'est la raison pour laquelle ce paquet vaut la peine d'être mis
dans un crochet de pré-commit : il tourne en quelques millisecondes, sans
bibliothèque d'images ni client de modèle derrière lui. Le reste du paquet
s'installe à côté, puisqu'il n'y a plus d'extras, et le lint n'en dépend
pas : `best-engine-ai-helper`, dont seul `--ai` se sert, n'est importé que
quand `--ai` le demande, et chaque règle tourne sans lui.

## Utilisation

### D'abord, passer le Markdown au crible

```sh
make-site lint docs/                 # sort 1 à la moindre erreur ; un avertissement ne fait pas échouer
make-site lint docs/ --fix           # répare ce qui a une réparation sûre
```

### Puis rendre, habiller, indexer

```sh
make-site html README.md --out site/
make-site html docs/ --out site/docs/
make-site icons logo.png --out site/icons/
make-site indexes --root site/ --base-url https://exemple.fr
make-site meta site/index.html       # demande un modèle local
```

### Et pour un site qui existe déjà — le vôtre ou celui d'un autre

Aucun Markdown n'est requis ici : l'auditeur lit le HTML posé, un dossier,
une page ou une URL vivante. `--fix` ne réécrit que ce qui se **dérive** de
ce que la page dit déjà ; le texte d'un titre, le choix d'une `og:image` ou
le corps d'un JSON-LD se rapportent avec la commande qui les rédige, jamais
ne s'écrivent tout seuls. Une URL distante se rapporte et ne se répare pas.

```sh
make-site audit public/ --base-url https://exemple.fr              # constat
make-site audit public/ --base-url https://exemple.fr --dry-run    # ce que --fix changerait
make-site audit public/ --base-url https://exemple.fr --fix --lang fr
make-site audit https://exemple.fr/a-propos                        # une page en ligne
```

Chaque règle cite sa spécification — WHATWG HTML, RFC 6596 pour `canonical`,
RFC 9309 pour `robots.txt`, sitemaps.org 0.9, ogp.me, les Cards de X,
JSON-LD 1.1, le Web App Manifest du W3C, le guide d'Apple, RFC 4287 et
RSS 2.0, llmstxt.org. Là où aucun document de ce genre n'existe, la règle le
dit au lieu de faire semblant. La table complète, règle par règle, est dans
`references/audit-site.md` : c'est elle qu'on cite quand un constat est
contesté.

### Mener le lecteur là où le site veut l'emmener

Moteurs de recherche, moteurs génératifs et moteurs de réponse (SEO, GEO,
AEO) finissent sur la même question : une fois le lecteur arrivé, que
doit-il faire ? C'est donc la première entrée, demandée et non devinée.

```sh
make-site cta site/                     # ce que le site propose, puis : lequel sert-il ?
make-site faq site/ > faq.md            # la FAQ qui manque, en brouillon
make-site faq site/ --audit --fix       # le FAQPage reconstruit depuis la FAQ visible
make-site findable site/ --base-url https://exemple.fr
make-site indexes --root site/ --base-url https://exemple.fr \
  --offer "Sous-titres locaux pour les équipes." --cta "Réserver une démo=https://cal.com/acme/demo"
```

Les CTA déclarés (`ctas.yaml`) désignent les *pages argent* : celles qui en
portent un dans leur corps, et celle où il mène. Un `noindex` y est une
erreur ; sur un billet, c'est un choix. Chaque réponse de la FAQ vient d'un
passage du site, et chaque nombre qu'elle contient de ce passage, sinon elle
n'est pas écrite : une question sans réponse dans le site va au rapport des
manques. Le balisage `FAQPage` est construit depuis le texte visible, une
fois par page, et jamais présenté comme un levier de classement : Google ne
montre plus de résultat enrichi FAQ depuis le 2026-05-07, et les moteurs de
réponse lisent ce que lit le lecteur.

### Et, si la page doit être lue à voix haute

```sh
make-site narrate billet.md --out-dir site/audio/
make-site readalong site/billet.html --narration site/audio/ --out built/
```

La voix elle-même vit dans [`sprezzature-audio`](https://github.com/warith-harchaoui/sprezzature-audio),
dont les moteurs tournent sur `speaker-helper` : ce paquet-ci possède le
**document** et la **page**, pas les moteurs. Quelqu'un qui veut seulement du
Markdown rendu ne charge jamais de pile de synthèse vocale pour l'obtenir.

### Depuis Python

```python
from sprezzature_publish import lint_file, convert_one
```

Un site se construit avec un script que quelqu'un a écrit, dans une boucle,
à heure fixe. Ce script doit importer plutôt que lancer une commande et
analyser sa sortie.

### Par HTTP

```sh
pip install "sprezzature-publish"
sprezzature-publish-mcp --port 8000     # les routes et /mcp, un seul processus
curl -s localhost:8000/health
```

`uvicorn sprezzature_publish.api:app` sert les routes seules : le point MCP
est monté quand `sprezzature_publish.mcp` est importé, ce que fait
`sprezzature-publish-mcp` avant d'écouter.

Sept routes — lint, audit, rendu, réécriture en langage clair, CTA, FAQ et le
rapport commun de trouvabilité — plus `GET /health`, parce que ce sont celles
qui traversent proprement une frontière réseau : du texte entre, du texte
sort. Le point MCP publie les mêmes huit comme outils, nommés par leur
`operation_id` (`lint_markdown`, `audit_site`, `render_markdown`,
`rewrite_plainly`, `find_calls_to_action`, `build_faq`, `report_findability`,
`health`). Les trois routes de niveau site prennent les pages sous la forme
`[{path, content}]` et les CTA déclarés en paramètre, et le disent dans la
réponse quand les CTA manquent. Le jeu de favicons est un dossier de binaires
indexés par nom de fichier : il reste une commande plutôt que d'être offert
ici avec un protocole de téléchargement inventé.

### En conteneur

```sh
docker compose up -d
curl -s localhost:8000/health
docker compose --profile prose up -d       # ajoute le serveur de modèle local
```

Le conteneur lance `sprezzature-publish-mcp`, donc un seul port sert les
routes HTTP et le point MCP : pointez un client MCP sur
`http://localhost:8000/mcp`.

Le serveur de modèle est un profil à part : seuls les outils qui interrogent
un modèle local en ont besoin, et qui ne veut que des pages ne doit pas être
obligé d'en faire tourner un.

## Ce qu'il ne possède pas

- **La voix** — `sprezzature-audio`, qui possède le son dans les deux sens :
  les sous-titres changent la parole en texte daté, la narration change le
  texte en son daté. Il est en dépendance de base, donc les voix arrivent
  avec `pip install sprezzature-publish` ; seuls les fichiers de modèle se
  téléchargent à part.
- **L'accessibilité de la page rendue** — `sprezzature-accessibility`.
- **Le contraste et les couleurs** — `sprezzature-colors`.
- **Les figures** — `sprezzature-figures`.

```sh
sprezzature-audio-install-voice --engine chatterbox    # les fichiers de modèle, une fois
sprezzature-publish-narrate post.md --out-dir site/audio/
```

Aucun moteur n'est nommé sur la deuxième ligne et aucun n'a besoin de l'être : le
routeur de speaker-helper le choisit d'après la langue et la condition hors
ligne, et il répond aujourd'hui Chatterbox en anglais comme en français, d'où
le moteur à installer. `--engine kokoro` prend le moteur léger exprès : il lit
le texte, reconnaît sa langue et choisit la voix qui la parle. Ce n'est pas
un confort : la langue détectée est ce dont part son phonétiseur, et une page
française lue comme de l'anglais n'est pas du français avec un accent
américain, c'est un Américain qui épelle les mots.

La frontière vaut d'être dite : ce paquet décide **quoi** publier et
**comment la page est faite**. Ce que la page contient d'audio, d'images ou de
graphiques appartient à ceux qui savent les produire.

## Voir aussi

- [`sprezzature`](https://github.com/warith-harchaoui/sprezzature) — la suite
- [`sprezzature-audio`](https://github.com/warith-harchaoui/sprezzature-audio) — les voix, et l'audit des sous-titres
- [`sprezzature-accessibility`](https://github.com/warith-harchaoui/sprezzature-accessibility) — relire le HTML émis, et rédiger le texte alternatif qu'il dit manquant
- [`sprezzature-ui`](https://github.com/warith-harchaoui/sprezzature-ui) — les composants

## Licence

BSD-3-Clause. Voir [LICENSE](LICENSE).

## Auteur

[Warith HARCHAOUI, Ph.D.](https://www.linkedin.com/in/warith-harchaoui/)
