# wcl-voix — les voix embarquées de WCL Play

Les voix que l'application **WCL Play** propose en lecture à voix haute, et de
quoi les fabriquer. Ce dépôt ne contient aucun modèle : il contient le
catalogue, le script qui va les chercher, et le mécanisme qui les publie.

Les fichiers, eux, vivent dans la [publication `v1`](../../releases/tag/v1),
que l'application interroge directement.

## Pourquoi ce dépôt existe

Une voix Piper pèse 60 à 110 Mo. Douze voix, c'est 700 Mo — impensable dans le
paquet d'un magasin d'applications, où chaque mégaoctet est un téléchargement
refusé sur un forfait limité. Les voix sont donc **servies à la demande** : on
en écoute un extrait, on télécharge celle qu'on aime, et elle reste sur le
téléphone. La lecture, ensuite, ne demande plus de réseau du tout.

## Ce que l'application attend

Des fichiers **plats**, sans archive : la première phase du projet a mesuré
37 secondes d'extraction `bz2` sur un OPPO d'entrée de gamme, pour rien.

```
manifest.json                 le catalogue (id, langue, genre, poids, empreinte, licence)
<pack>.onnx                   le modèle
<pack>.tokens.txt             ses jetons
<pack>.<locuteur>.extrait.wav quelques secondes, à écouter avant de télécharger
espeak-ng-data.zip            les données de prononciation, communes à toutes les voix
```

Un même modèle peut porter **deux voix** (`fr_FR-upmc-medium` contient Jessica
et Pierre) : la clé d'une voix est `<pack>#<locuteur>`, un seul téléchargement
sert les deux.

## Fabriquer et publier

```bash
python publier.py --verifier   # licences et locuteurs, sans rien télécharger
python publier.py --preparer   # télécharge, extrait, rend les extraits, écrit le manifeste
python publier.py --publier    # + envoie tout dans la publication v1
```

En pratique, cela tourne sur GitHub Actions (*Publier les voix*, déclenchement
manuel) : 700 Mo descendus puis remontés n'ont rien à faire sur une connexion
domestique.

## Les licences ne sont pas une formalité

WCL vend des abonnements. Une voix entraînée sur un jeu de données **non
commercial** ou **AGPL** ne peut pas y entrer, quelle que soit sa qualité —
c'est ce qui a écarté `tom` (AGPLv3), `ryan` et `hfc_*` (CC BY-NC-SA), et
`lessac` (licence Blizzard, recherche seulement).

`publier.py` relit la ligne de licence du `MODEL_CARD` en amont à chaque
publication et **s'arrête si elle a changé** depuis ce que `catalogue.json` a
enregistré. Une licence qui bouge ne doit pas passer inaperçue.

Chaque voix affiche sa licence et son jeu de données dans l'application, et
dans les notes de la publication : c'est ce que CC-BY demande.
