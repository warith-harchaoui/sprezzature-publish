# Paysage

La plupart des comparaisons de générateurs de sites les classent, et le
classement masque la seule chose qui décide vraiment : **quelle taille fait le
site, et pour qui.**

Un générateur taillé pour cent pages versionnées avec son écosystème de
greffons n'est pas une version moins bonne de ce paquet ; c'est un autre
outil, et pour ce site-là c'est le bon. `sprezzature-publish` est dimensionné
pour un site qu'on tient dans sa tête — un README, quelques pages, un blog —
et tout ce qu'il fait bien découle de cette contrainte.

## La table, franchement

Ce sont des **jugements**, pas des mesures : un 5 veut dire « c'est une force
de cet outil en octobre 2026 », un 1 « il ne fait pas vraiment ça ». Ils sont
écrits pour qu'on puisse contester un chiffre précis plutôt qu'une impression.

| Outil | Simplicité de mise en route | Taille de site | Balises et index inclus | Tourne hors ligne | Narration et suivi | Taille de l'écosystème |
|---|---|---|---|---|---|---|
| **sprezzature-publish** | 5 | 2 | 5 | 5 | 5 | 1 |
| MkDocs Material | 4 | 5 | 3 | 4 | 1 | 4 |
| Hugo | 2 | 5 | 2 | 4 | 1 | 5 |
| Astro | 2 | 5 | 3 | 4 | 1 | 5 |
| Jekyll | 3 | 4 | 2 | 4 | 1 | 4 |
| Eleventy | 3 | 4 | 2 | 4 | 1 | 3 |
| Docusaurus | 2 | 5 | 3 | 4 | 1 | 4 |

La source est dans [`assets/landscape.csv`](assets/landscape.csv).

## La carte

![Carte de positionnement](assets/sprezzature_publish.png)

Produite avec [`standpoint`](https://github.com/warith-harchaoui/standpoint)
à partir de la table ci-dessus :

```sh
standpoint assets/landscape.csv --outdir assets
```

La géométrie est une ACP de corrélation ordinaire, donc **déterministe** : la
même table donne la même carte à chaque exécution, quel que soit le modèle qui
a nommé les axes. Deux axes portent environ **95 %** de l'information, ce qui
est beaucoup et signifie que les six critères ne sont pas indépendants : les
outils faciles à mettre en route sont aussi, ici, ceux dont l'écosystème est
petit.

À lire comme un résumé, pas comme une preuve. La carte projette fidèlement la
table ; la table est un ensemble d'opinions. `standpoint` écrit aussi une
interprétation en prose — elle n'est pas reproduite ici, parce qu'un modèle
qui relit des notes écrites par quelqu'un n'est pas une découverte, et ce
fichier est plus utile si les jugements restent visiblement les miens.

## Ce que la forme dit vraiment

**L'échange, c'est la taille contre tout le reste.** Les trois critères où ce
paquet marque le plus — balises et index inclus, hors ligne, narration — sont
trois choses qu'un petit site veut et qu'un gros règle par des greffons. Le
critère où il marque le moins, la taille de l'écosystème, est celui dont un
gros site ne peut pas se passer.

**La narration est la seule colonne où le champ est vide.** Tous les autres
marquent 1, et pas par retard : lire une page à voix haute avec une piste
temporisée qui surligne la phrase prononcée n'est une fonction de générateur
de site nulle part ailleurs. C'est cette colonne qui fait que ce paquet existe
*à côté* des autres plutôt qu'à leur place.

**« Tourne hors ligne » est presque plat**, et cette platitude est honnête. La
plupart des générateurs tournent hors ligne. Ce qui diffère, c'est de savoir
si les *balises* et la *réécriture en langage clair* le font aussi — et ici
oui, le modèle est local.

## Quand prendre autre chose

- **Cent pages versionnées, un écosystème, une équipe** — MkDocs Material,
  Docusaurus, Astro. Ils font ça mieux, et le README de ce paquet le dit.
- **La vitesse de construction avant tout** — Hugo.
- **Un site Jekyll existant** — laissez-le là.
- **Vous voulez un éditeur hébergé** — ce n'est pas la bonne famille.

## Voir aussi

- [`speaker-helper`](https://github.com/warith-harchaoui/speaker-helper) — la
  voix que ce paquet orchestre sans la posséder.
- [`sprezzature-accessibility`](https://github.com/warith-harchaoui/sprezzature-accessibility)
  — la page produite est-elle utilisable.
