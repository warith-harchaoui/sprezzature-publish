# sprezzature-publish

[🇫🇷](https://github.com/warith-harchaoui/sprezzature-publish/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/sprezzature-publish/blob/main/README.md)

Un dossier de Markdown devient un site que quelqu'un peut trouver.

Pointez-le sur un `README.md` et un dossier `docs/` : il en sort des pages,
les balises qui les rendent partageables, un jeu de favicons et d'icônes
d'application à partir d'un seul logo, les index que les robots et les
modèles de langue vont chercher — `robots.txt`, `sitemap.xml`, `llms.txt`, un
flux Atom, `humans.txt` — et, si on le demande, une narration audio avec un
suivi qui surligne la phrase en train d'être lue.

Il est taillé pour un site qu'on tient dans sa tête : un README, quelques
pages de documentation, un blog. Pour cent pages versionnées, prenez MkDocs
Material, Hugo ou Astro ; celui-ci ne les concurrence pas et le dit.

---

## Ce qu'il y a dedans

| | |
|---|---|
| `sprezzature-publish-lint` | **audit** — lire le Markdown avant que quoi que ce soit ne le rende. Bibliothèque standard seule, quelques millisecondes, taillé pour un crochet de pré-commit. `--fix` répare ce qui a une réparation sûre. |
| `sprezzature-publish-html` | Markdown → pages HTML autonomes, diagrammes Mermaid rendus. |
| `sprezzature-publish-icons` | un logo → favicon, icônes d'application, icônes PWA, et le fragment de `<head>` qui les référence. |
| `sprezzature-publish-indexes` | `robots.txt`, `sitemap.xml`, `llms.txt`, `llms-full.txt`, Atom, `humans.txt`. |
| `sprezzature-publish-meta` | Open Graph, Twitter Card et Schema.org JSON-LD, rédigés par un modèle local. |
| `sprezzature-publish-plain` | réécrire la prose à un niveau de lecture visé, en gardant les termes que vous nommez. |
| `sprezzature-publish-changelog` | un `CHANGELOG.md` devient des billets datés et un flux. |
| `sprezzature-publish-narrate` | narrer un billet avec une voix locale, et écrire la piste temporisée à côté de l'audio. |
| `sprezzature-publish-readalong` | lier cette narration à la page, pour que la phrase prononcée soit surlignée. |

Deux portes d'entrée sur les neuf : `make-site <outil>` (argparse) et
`sprezzature-publish <outil>` (click). Les deux lisent **une seule** table,
donc un outil ne peut pas apparaître dans l'une et manquer dans l'autre.

## Installation

```sh
pip install sprezzature-publish              # le lint : aucune dépendance
pip install "sprezzature-publish[html]"      # + le moteur de rendu
pip install "sprezzature-publish[icons]"     # + Pillow, pour le jeu d'icônes
pip install "sprezzature-publish[prose]"     # + les outils à modèle local
pip install "sprezzature-publish[all]"       # tout ce qui précède
pip install "sprezzature-publish[api,mcp]"   # + les surfaces HTTP et agent
```

Que le lint n'ait **aucune dépendance** est délibéré, et c'est la raison pour
laquelle ce paquet vaut la peine d'être mis dans un crochet de pré-commit : il
tourne en quelques millisecondes dans un conteneur minimal, sans bibliothèque
d'images ni client de modèle derrière lui. Tout ce qui est plus lourd est un
extra, nommé d'après l'outil qui en a besoin, pour qu'une installation dise à
quoi elle sert.

## Utilisation

### D'abord, passer le Markdown au crible

```sh
make-site lint docs/                 # sort non nul au moindre constat
make-site lint docs/ --fix           # répare ce qui a une réparation sûre
```

### Puis rendre, habiller, indexer

```sh
make-site html README.md --out-dir site/
make-site icons logo.png --out-dir site/icons/
make-site indexes site/ --base-url https://exemple.fr
make-site meta site/index.html       # demande un modèle local
```

### Et, si la page doit être lue à voix haute

```sh
make-site narrate billet.md --out-dir site/audio/
make-site readalong site/billet.html --narration site/audio/
```

La voix elle-même vit dans [`speaker-helper`](https://github.com/warith-harchaoui/speaker-helper) :
ce paquet-ci possède le **document** et la **page**, pas les moteurs. Quelqu'un
qui veut seulement du Markdown rendu ne doit pas avoir à installer une pile de
synthèse vocale pour l'obtenir.

## Ce qu'il ne possède pas

- **La voix** — `speaker-helper`. Les moteurs, la timeline, les cues.
- **L'accessibilité de la page rendue** — `sprezzature-accessibility`.
- **Le contraste et les couleurs** — `sprezzature-colors`.
- **Les figures** — `sprezzature-figures`.

La frontière vaut d'être dite : ce paquet décide **quoi** publier et
**comment la page est faite**. Ce que la page contient d'audio, d'images ou de
graphiques appartient à ceux qui savent les produire.

## Voir aussi

- [`sprezzature`](https://github.com/warith-harchaoui/sprezzature) — la suite
- [`speaker-helper`](https://github.com/warith-harchaoui/speaker-helper) — la voix
- [`sprezzature-ui`](https://github.com/warith-harchaoui/sprezzature-ui) — les composants

## Licence

BSD-3-Clause. Voir [LICENSE](LICENSE).

## Auteur

[Warith HARCHAOUI](https://warith-harchaoui.github.io/) —
warithmetics@deraison.ai
