# Paysage

`sprezzature-publish` est la brique de publication de la suite
[sprezzature](https://sprezzature.ai/) : un dossier de Markdown entre, un site
qu'on peut trouver sort. Les pages, les balises méta qui décident de ce à quoi
ressemble un lien partagé, un jeu de favicons et d'icônes d'application depuis
un seul logo, les index que cherchent les robots et que lisent les modèles de
langue, et une narration liée à la page phrase à phrase.

Elle est dimensionnée pour un site qu'on tient dans la tête : un README,
quelques pages de documentation, un blog. Cette contrainte est la première
chose à dire, parce que tout ce qui suit en découle.

## Sa place dans l'écosystème

```
suite sprezzature
├── sprezzature-publish        ← ce paquet (10 outils, document → site)
├── sprezzature-accessibility  (auditer le HTML produit ici, rédiger l'alt manquant)
├── sprezzature-audio          (les voix, et l'audit des sous-titres)
├── sprezzature-colors         (contraste et déficience de la vision des couleurs)
├── sprezzature-figures        (167 types de graphiques, SVG écrit ligne à ligne)
├── sprezzature-maps           (de vrais traits de côte sur une vraie projection)
├── sprezzature-ui             (l'écran, et le catalogue de traduction)
├── sprezzature-ux-laws        (30 lois, 8 décidables depuis le balisage)
├── sprezzature-video          (ce qu'un film affirme, confronté au code)
└── best-engine-ai-helper      (quel modèle local tient sur cette machine)
```

**Avant elle :** celui qui a écrit le Markdown. Un README, un dossier `docs/`,
un `CHANGELOG.md`, un fichier de logo. Rien d'autre n'est requis, et l'audit
du Markdown tourne avant que quoi que ce soit ne le rende.

**Après elle :**
[`sprezzature-accessibility`](https://github.com/warith-harchaoui/sprezzature-accessibility),
qui lit le HTML produit ici et dit s'il est utilisable, puis rédige le texte
alternatif qu'il a trouvé manquant. Les deux ne se recouvrent pas, et c'est
voulu : ce paquet vérifie `og:image:alt`, qui est une surface d'aperçu social,
et laisse toutes les images à l'intérieur de la page à l'autre.

**La brique sœur qui fait le travail voisin :**
[`sprezzature-audio`](https://github.com/warith-harchaoui/sprezzature-audio),
qui possède la modalité sonore dans les deux sens. Les sous-titres
transforment de la parole enregistrée en texte daté ; la narration transforme
du texte écrit en son daté. Ce paquet ne synthétise pas un seul échantillon.
Il appelle l'autre en sous-processus, pour qu'un lecteur qui veut seulement du
Markdown rendu n'installe jamais une pile de synthèse vocale.

## Quand la choisir

- **Vous avez un README et un dossier `docs/` et vous voulez les mettre en
  ligne cet après-midi**, avec les balises méta, le jeu d'icônes et le
  `sitemap.xml` déjà corrects plutôt que classés en travail à faire.
- **Un site existe déjà et personne ne peut le régénérer.** Une page exportée
  par un graphiste, une page d'accueil en ligne depuis trois ans, un export
  WordPress. Il n'y a pas de Markdown où revenir, et
  `sprezzature-publish-audit` n'en demande pas : il prend un répertoire, un
  fichier ou une URL en ligne, dit ce qu'un robot d'indexation ne trouvera
  pas, et avec `--fix` réécrit uniquement ce qui se déduit de ce que la page
  dit déjà. C'est le dixième outil et le plus récent : il est dans le dépôt
  et pas encore dans la roue publiée, qui est la `1.3.0`.
- **Le Markdown doit passer un contrôle avant d'être rendu.** L'audit du
  Markdown n'a aucune dépendance, pas même une bibliothèque d'images, ce qui
  lui permet de tenir dans un crochet de pré-commit et de tourner en
  millisecondes dans un conteneur minimal.
- **Un article doit pouvoir s'écouter, et l'auditeur doit pouvoir suivre sur
  la page.** La narration tourne sur votre machine, et la lecture suivie
  qu'elle lie est vérifiée repère par repère contre la page rendue, pas
  supposée.

## Quand prendre autre chose

- **Cent pages versionnées, un écosystème d'extensions, une équipe.**
  [MkDocs Material](https://squidfunk.github.io/mkdocs-material/),
  [Docusaurus](https://docusaurus.io/) et
  [Starlight](https://starlight.astro.build/) font cela mieux dans toutes les
  directions qui comptent : navigation versionnée, recherche, un thème
  maintenu par quelqu'un d'autre, des contributeurs qui connaissent déjà les
  conventions. Ce paquet le dit dans son propre README et ne cherche pas à
  rivaliser.
- **La vitesse de construction avant tout, ou un binaire unique sans moteur
  d'exécution.** [Hugo](https://gohugo.io/) et
  [Zola](https://www.getzola.org/). Hugo embarque en plus le routage
  multilingue, `sitemap.xml` et RSS sans extension, soit trois des colonnes de
  ce paquet répondues par l'outil que vous alliez utiliser de toute façon.
- **Un design que vous contrôlez ligne à ligne, avec des îlots
  d'interactivité.** [Astro](https://astro.build/) ou
  [Eleventy](https://www.11ty.dev/). Ce paquet produit un seul gabarit et
  n'offre aucune couche de thème.
- **De la documentation hébergée pour vous, avec `llms.txt` produit tout seul
  et rien à installer.** [Mintlify](https://www.mintlify.com/) et
  [GitBook](https://gitbook.com/) font cela, et Mintlify publie `llms.txt`,
  `llms-full.txt` et un jumeau Markdown de chaque page depuis novembre 2024.
  Si un compte et une construction hébergée sont acceptables, c'est moins de
  travail que n'importe quelle chaîne locale.
- **Une voix pour n'importe quoi, dans n'importe quelle langue.**
  [ElevenReader](https://elevenlabs.io/text-reader) et
  [Speechify](https://speechify.com/) lisent un PDF, un courriel ou une page
  dont aucun système de construction n'a jamais entendu parler, dans plus de
  langues que ce paquet n'a de libellés de lecteur, et avec un surlignage au
  mot plutôt qu'à la phrase. Ce sont des produits ; ceci est une étape de
  construction.
- **Un style de prose imposé à toute une documentation.**
  [Vale](https://vale.sh/) est un binaire unique hors ligne, avec un langage
  de règles, des mesures de lisibilité et un grand jeu de guides de style
  publiés. L'outil de langue claire ici réécrit ; Vale mesure et impose, ce
  qui est un autre métier, et celui qu'une équipe de documentation veut
  d'abord.

## Les idées à prendre

Étudier un concurrent et ne rien rapporter, c'est de la lecture perdue. Huit
choses que ces outils font, classées par ce qu'elles rendent rapporté à ce
qu'elles coûtent. Deux sont des refus, et la raison est l'entrée.

**[Mintlify](https://www.mintlify.com/) et la proposition `llms.txt` v2 : le
jumeau Markdown, déclaré.** Mintlify publie une copie `.md` de chaque page à
côté du HTML et pointe `llms.txt` vers la copie, pour qu'un agent reçoive de
la prose propre, sans navigation et sans scripts ; la v2 de la proposition
(août 2026) nomme le mécanisme, `rel="alternate" type="text/markdown"`. Ici :
`md_to_html.py` écrirait `page.md` à côté de `page.html` et ajouterait ce lien
dans l'en-tête, `site_indexes.py` lierait le `.md` depuis `llms.txt` au lieu
de la page rendue, et `audit_site.py` gagnerait un `SITE107` qui vérifie que
le jumeau existe et que le lien le déclare. Coût : une demi-journée sur le
chemin Markdown, où la source est déjà en main. Limite honnête : une page
auditée sans Markdown derrière elle ne peut pas avoir de jumeau, donc la règle
doit y être une note et pas une erreur, exactement comme `SITE014` déjà.

**[Vale](https://vale.sh/) : le niveau de lecture comme mesure, pas comme
indication dans une consigne.** Vale livre la lisibilité sous forme de règles
(Flesch-Kincaid, Gunning fog, SMOG, LIX, Coleman-Liau, ARI), calculées de
façon déterministe sans aucun modèle à proximité. Ici : `plain_language.py`
prend `--target-grade 8`, le passe dans une consigne, puis vérifie seulement
que la sortie n'est pas plus longue que l'entrée. Un drapeau `--report`
affichant le niveau mesuré avant et après donnerait un sens au drapeau. C'est
le meilleur rapport de la liste précisément parce que la brique a déjà le
drapeau et rien derrière. Coût : un après-midi, bibliothèque standard, aucune
dépendance nouvelle. La réserve honnête : le comptage des syllabes est
approximatif en anglais et davantage en français, donc le nombre est une
estimation annoncée et doit le dire.

**Le greffon social de
[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/plugins/social/) :
une carte d'aperçu par page, rendue localement.** Il dessine un PNG de
1200 × 630 depuis le titre de la page et le livre comme `og:image`, mis en
cache dans le répertoire du site pour que rien ne dépende d'un service
externe. Ici, `SITE008` signale un `og:image` manquant et refuse d'en
inventer un, ce qui est correct et aussi le constat le plus fréquent sur un
site neuf. `favicons.py` a déjà Pillow, le logo, le fond et les deux couleurs
de thème : une exécution `--cards` écrivant `og/<page>.png` transformerait ce
refus en réparation déduite, ce qui est la ligne de partage que `audit_site.py`
trace déjà. Coût : un après-midi, dans un extra que les gens qui installent
les icônes ont déjà. Ce qui l'empêche d'être gratuit : une carte a besoin
d'une fonte embarquée, et une fonte est une question de licence.

**[Hugo](https://gohugo.io/) : le sitemap multilingue.** Hugo écrit des
entrées `xhtml:link rel="alternate" hreflang=…` pour qu'un robot sache quelle
page est l'autre langue de quelle page, au lieu de le déduire d'un chemin.
Ici : `site_indexes.py` écrit une liste `<url><loc>` nue, et le site de la
suite elle-même est en anglais et en français. Un drapeau `--hreflang`
appariant `/fr/x.html` à `/x.html` par convention de chemin, plus une règle
par site qui signale une traduction non appariée, comble un trou qui tient
plus du rapport de bogue que de l'idée. Coût : un après-midi, aucune
dépendance, et le format est documenté par Google plutôt que par
sitemaps.org, ce que la table des règles doit dire.

**[Yoast SEO](https://yoast.com/) : un seul `@graph`, pas plusieurs blocs.**
Yoast émet un unique bloc JSON-LD dont les nœuds (`WebSite`, `WebPage`,
`Organization`, `Person`, `BreadcrumbList`) se référencent entre eux par
`@id`, au lieu d'être dispersés dans des balises indépendantes. Ici :
`meta_from_ollama.py` demande un seul objet à un modèle local. Lui donner un
squelette `@graph` fixe à remplir rend sa tâche plus petite et non plus
grande, et permet à `SITE011` de vérifier quelque chose de réel : que chaque
`@id` référencé dans le document se résout dans ce document. Coût : une
demi-journée, un changement de consigne et un schéma. Cela réduit aussi ce
que le modèle peut rater, ce qui est la direction que ce paquet prend partout
ailleurs.

**Le vérificateur de
[RealFaviconGenerator](https://realfavicongenerator.net/) : ouvrir l'icône, et
pas seulement la trouver.** Il lit un site publié et dit, plateforme par
plateforme, quelle déclaration manque et laquelle pointe vers un fichier qui
n'est pas ce qu'il prétend. Ici : `SITE110` et `SITE111` vérifient que les
fichiers existent et `SITE112` que l'extrait `head.html` a bien été collé,
mais rien n'ouvre une icône pour confirmer qu'elle se décode et qu'elle fait
la taille que le `<link>` déclare, ce qui est exactement la façon dont un jeu
recopié à la main casse. Coût : une objection réelle, pas petite. L'audit est
l'un des deux outils qui tournent sans rien d'installé, et lire un PNG veut
dire Pillow. La forme qui survit est un `--check-icons` facultatif qui nomme
ce dont il a besoin et s'abstient sans lui.

**Le `llms-small.txt` de
[starlight-llms-txt](https://delucis.github.io/starlight-llms-txt/) : refusé.**
Le greffon écrit une troisième variante, allégée pour les petites fenêtres de
contexte, à côté de `llms.txt` et `llms-full.txt`. Non retenu. `llms.txt` est
une proposition et pas une norme, et `llms-full.txt` est déjà une convention
que la proposition elle-même ne mentionne pas ; un troisième nom de fichier
inventé serait ce paquet en train d'écrire un fichier que personne ne cherche
par son nom. La moitié utile de l'idée existe déjà sous la forme de
`--no-llms-full`, qui laisse l'appelant décider de ce qu'il publie.

**[Speechify](https://speechify.com/) et
[ElevenReader](https://elevenlabs.io/text-reader) : le surlignage au mot,
refusé ici.** Les deux surlignent le mot prononcé, pas la phrase, et cela se
lit mieux. Non retenu, pour une raison qui est toute la conception du module :
les repères de phrase sortent de la synthèse elle-même, donc la page et
l'audio se comparent un à un et la construction s'arrête à la première
divergence. Des temps au mot demanderaient des horodatages par jeton depuis le
moteur, ou un aligneur forcé, dont aucun ne se vérifie de la même façon, et la
seule garantie de cette fonction est que le surlignage n'est jamais décalé
d'une phrase. Si cela se prend un jour, c'est dans `sprezzature-audio`, qui
possède le temps dans les deux sens.

## Comment le domaine se découpe

**Générateurs, composants, produits.** Un générateur de site statique (Hugo,
Astro, Eleventy, Jekyll, Zola, Pelican, Quarto, mdBook) possède toute la
chaîne, d'un dossier de contenu à un répertoire de HTML, et traite les
métadonnées comme quelque chose qu'on configure dans sa couche de gabarits. Un
composant de référencement (next-seo, astro-seo, jekyll-seo-tag, Yoast SEO) ne
possède que le `<head>` et suppose qu'un site existe déjà autour de lui. Un
produit hébergé (Mintlify, GitBook) possède la construction, l'hébergement et
la recherche, et demande un compte. Ce paquet est à cheval sur les deux
premiers : il produit des pages, et il entre aussi dans un site qu'il n'a pas
construit pour en réparer l'en-tête.

**Local contre hébergé, et ce n'est pas une question de licence.** Tous les
générateurs de la table tournent sur votre machine ; Vale et
pwa-asset-generator aussi. La ligne qui compte est plus étroite : où se prend
le *jugement*. Les descriptions méta, les réécritures en langue claire et les
textes alternatifs sont les parties qu'on sous-traite à un service, et c'est
le seul endroit où ce paquet impose un modèle local, résolu par
[`best-engine-ai-helper`](https://github.com/warith-harchaoui/best-engine-ai-helper)
pour qu'aucun script d'ici ne nomme une étiquette de modèle. Mintlify,
GitBook, ElevenReader, Speechify et NotebookLM envoient tous le texte quelque
part. Pour un README public, cela ne gêne personne ; pour un document interne,
cela tranche la question.

**Du texte qui entre, du son qui sort.** La moitié narration de cette table ne
recouvre presque pas la moitié générateurs. ElevenReader, Speechify,
NotebookLM et [Podcastfy](https://github.com/souzatharsis/podcastfy) lisent un
document à voix haute et aucun ne construit de site ; aucun générateur de site
statique de la table ne lit quoi que ce soit à voix haute. La colonne de la
lecture suivie est l'endroit où les deux moitiés se touchent, et elle est
presque vide : les lecteurs grand public le font dans leur propre application,
sur une page qu'ils sont allés chercher, et ce paquet le fait en écrivant du
balisage dans une page que vous hébergez ensuite vous-même. Personne d'autre
n'écrit un `<track kind="metadata">` à côté de votre propre HTML et ne l'y
laisse.

**La colonne neuve est `llms.txt`, et elle est contestée.** Proposée par
Jeremy HOWARD en septembre 2024 et révisée en v2 en août 2026, c'est une
convention, pas une norme. Les mesures indépendantes de 2026 situent
l'adoption entre 5,6 % et 13,3 % des domaines échantillonnés selon
l'échantillon, et la documentation de Google sur la recherche générative du
15 mai 2026 la range parmi les tactiques qu'elle juge inutiles. Mintlify et
GitBook la produisent automatiquement, Starlight a un greffon très utilisé,
Nextra n'a rien. Ce paquet l'écrit, et la règle qui la vérifie dit dans
`references/audit-site.md` que c'est une proposition et pas un document
d'organisme de normalisation, parce que c'est le niveau de revendication
honnête.

## La table

Vingt-six outils, quinze critères. Une étoile est un **jugement**, pas une
mesure : 5 veut dire que c'est une force de cet outil en octobre 2026, 1 qu'il
ne fait pas vraiment cela. Chaque colonne est orientée pour que plus d'étoiles
soit meilleur, c'est pourquoi l'axe du coût se lit en ouverture et l'axe du
poids se lit en légèreté. Les notes sont écrites pour qu'on puisse contredire
une case précise plutôt qu'une impression.

`sprezzature-publish` est la première ligne parce que `standpoint` oriente
toute la carte autour de la première ligne et la place en haut à droite. C'est
une convention de dessin, pas une prétention de qualité, et la ligne perd
franchement sur quatre colonnes : elle ne tient pas au-delà de cent pages,
elle n'a aucune couche de thème, son lecteur parle deux langues et refuse les
autres, et c'est le paquet d'un seul auteur, vieux de quelques mois.

| Outil | Balises méta par page, sans extension | Jeu d'icônes depuis un seul logo | Index que cherchent les robots | Index que lisent les modèles de langue | Flux de syndication | Narration audio | Lecture suivie phrase à phrase | Réécriture en langue claire | S'applique à du HTML déjà publié | Local et hors ligne, sans compte | Installation légère | Tient au-delà de cent pages | Thèmes et personnalisation | Bilingue et parité | Maturité et écosystème |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| sprezzature-publish | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ |
| MkDocs Material | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Hugo | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Astro | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Starlight | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Docusaurus | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Eleventy | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Jekyll | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Zola | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| VitePress | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Nextra | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Quarto | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Pelican | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| mdBook | ⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| Mintlify | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| GitBook | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| next-seo | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Yoast SEO | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| RealFaviconGenerator | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ |
| pwa-asset-generator | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ |
| Vale | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Hemingway Editor | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ |
| ElevenReader | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Speechify | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| NotebookLM | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Podcastfy | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ |

## La carte

![Carte de positionnement de 26 outils de publication, de métadonnées, de prose et de narration. sprezzature-publish est seul dans le quadrant supérieur droit, très à droite de tout ce qui se trouve à sa hauteur. À son niveau mais sur l'axe central se tiennent les produits de lecture Speechify et ElevenReader, avec NotebookLM et Podcastfy juste en dessous et à leur gauche. Le bord gauche, près de l'axe horizontal, porte les outils à usage unique Hemingway Editor, RealFaviconGenerator, pwa-asset-generator et Vale. Toute la moitié basse est la famille des générateurs de sites statiques : Hugo, Docusaurus, Astro, Starlight, MkDocs Material, Jekyll, Quarto et Zola vers la droite, Eleventy, Nextra, Pelican, mdBook et next-seo vers la gauche, avec les produits hébergés Mintlify et GitBook et l'extension Yoast SEO sur le bord droit sous l'axe. mdBook, le plus faible dans l'ensemble, est en diagonale opposée à la référence. L'axe horizontal oppose l'autonomie à gauche à l'accessibilité à droite, l'accessibilité voulant dire ici les fichiers qui rendent un document trouvable. L'axe vertical oppose en bas un système de construction qu'on configure, en haut un outil qui agit sur un document que le lecteur tient déjà.](assets/paysage.svg)

La source est [`assets/paysage.csv`](assets/paysage.csv), la table en étoiles
ci-dessus et rien de plus, et la carte se régénère avec :

```sh
python scripts/landscape_to_csv.py ~/sprezzature-publish/PAYSAGE.md --out ~/sprezzature-publish/assets/paysage.csv
standpoint assets/paysage.csv --outdir assets --stem paysage --check
```

La géométrie est une analyse en composantes principales (ACP) sur
corrélations, et elle est **déterministe** : la même table donne la même carte
à chaque exécution, quel que soit le modèle qui a nommé les pôles. Les quatre
mots des bords viennent d'un modèle local ; les charges sont le contrôle, et
elles sont plus précises que les mots, donc voici de quoi les deux axes sont
faits.

**Horizontal, « Autonomie ↔ Accessibilité », 37,4 % de la variance.** Les
index que lisent les modèles de langue (+0,49), les index que cherchent les
robots (+0,42), les balises méta par page (+0,38) et la parité bilingue
(+0,37) tirent à droite ; « local et hors ligne » (−0,16) tire à gauche, et
c'est la chose qui tire le plus fort de ce côté. L'axe n'oppose donc pas
vraiment l'autonomie à l'accessibilité : il demande **est-ce que cet outil
écrit les fichiers qui rendent un document trouvable, oui ou non**. Le pôle
gauche est surtout l'absence de ce travail, et c'est pour cela que Hemingway
Editor (−3,01) et pwa-asset-generator (−2,35) sont là-bas. Mintlify est
exactement à la même abscisse que ce paquet, 3,01, ce qui est la carte en
train de constater qu'un produit de documentation hébergé et celui-ci
répondent à la même question par des moyens opposés.

**Vertical, « Solidité ↔ Fluidité », 17,8 % de la variance.** S'applique à du
HTML déjà publié (+0,41), narration audio (+0,40), lecture suivie (+0,37) et
réécriture en langue claire (+0,25) chargent vers le haut ; tient au-delà de
cent pages (−0,34), thèmes et personnalisation (−0,33) et local et hors ligne
(−0,25) chargent vers le bas. L'opposition réelle est **un système de
construction qu'on configure** contre **un outil qui agit sur un document que
quelqu'un tient déjà**. Tous les générateurs de sites statiques de la table
tiennent dans une bande entre −3,7 et −1,7 ; Speechify et ElevenReader sont à
+3,68 et +3,63. Ce paquet est à +3,68, donc du côté des lecteurs et pas des
générateurs, et c'est la bonne lecture de ce qu'il est.

Un détail à dire parce qu'il n'est pas flatteur : **« local et hors ligne »
charge négativement sur les deux axes**, donc tire vers le bas à gauche. Ce
paquet y marque 5 et se trouve quand même en haut à droite. Ce n'est pas le
fait d'être local qui l'y met ; c'est d'écrire les index et de lier la
narration.

**Deux axes portent 55,2 % de la table.** Près de la moitié de ce que disent
ces quinze critères n'est pas sur cette page, ce qui est attendu avec quinze
critères sur vingt-six outils, et c'est la raison pour laquelle la table reste
au-dessus de la carte et non en dessous. `--check` rapporte
`leader_top_right: True` et `axis_labels_visible: True`, et `readable: False` :
cinq paires d'étiquettes risquent de se chevaucher (Hugo et Docusaurus, Jekyll
et Quarto, Zola et VitePress, Nextra et Pelican, ElevenReader et Speechify).
C'est un effet d'encombrement de treize générateurs partageant une seule
bande, pas un défaut de géométrie, et les coordonnées derrière chaque
étiquette sont dans [`assets/paysage.yaml`](assets/paysage.yaml).

`standpoint` écrit aussi une interprétation en prose à côté de la figure. Elle
n'est pas reprise ici, parce qu'un modèle qui relit des notes écrites par
quelqu'un n'est pas un résultat, et que ce fichier est plus utile si les
jugements restent visiblement les miens. Sur cette exécution, le modèle local
n'a d'ailleurs pas répondu dans le temps imparti et le fichier d'analyse le
dit lui-même ; le nommage des axes, lui, est bien passé, et c'est la seule
chose qui soit reprise ci-dessus.

## Sources

- [llms.txt, la proposition](https://llmstxt.org/) de Jeremy HOWARD, v2, août 2026.
- [State of llms.txt 2026: adoption, standards, and practice](https://presenc.ai/research/state-of-llms-txt-2026).
- [Docs platforms that generate llms.txt automatically (2026)](https://context7.com/llms-txt-documentation-platforms).
- [Mastering generative engine optimization in 2026](https://searchengineland.com/mastering-generative-engine-optimization-in-2026-full-guide-469142), Search Engine Land.
- [Static site generators 2026 head-to-head](https://www.youngju.dev/blog/culture/2026-05-14-static-site-generators-2026-hugo-eleventy-astro-mkdocs-docusaurus-mintlify-starlight-comparison-deep-dive.en).
- [Material for MkDocs, le greffon social intégré](https://squidfunk.github.io/mkdocs-material/plugins/social/).
- [`starlight-llms-txt`](https://delucis.github.io/starlight-llms-txt/).
- [W3C Web Application Manifest, masques d'icônes](https://www.w3.org/TR/appmanifest/#icon-masks).
- [pwa-icons, un générateur d'icônes d'application web progressive plus rapide](https://github.com/SivaramPg/pwa-icons).
- [Podcastfy, une alternative open source à la fonction podcast de NotebookLM](https://github.com/souzatharsis/podcastfy).
