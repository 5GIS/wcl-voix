# Voix WCL - v1

Les voix embarquees de l'application WCL Play : des modeles Piper
(VITS), joues hors ligne par sherpa-onnx. Elles se telechargent depuis
l'application, une par une, avec un extrait a ecouter avant.

## Origine et licences

| Voix | Langue | Licence | Jeu de donnees |
| --- | --- | --- | --- |
| Siwis (`fr_FR-siwis-medium` #0) | fr | CC-BY 4.0 | https://datashare.is.ed.ac.uk/handle/10283/2353 |
| Jessica (`fr_FR-upmc-medium` #0) | fr | CC-BY-SA 4.0 | https://github.com/marytts/upmc-pierre-data |
| Pierre (`fr_FR-upmc-medium` #1) | fr | CC-BY-SA 4.0 | https://github.com/marytts/upmc-pierre-data |
| Gilles (`fr_FR-gilles-low` #0) | fr | CC0 | https://huggingface.co/datasets/rhasspy/piper-checkpoints |
| Kristin (`en_US-kristin-medium` #0) | en | Domaine public | https://huggingface.co/datasets/rhasspy/piper-checkpoints |
| Alba (GB) (`en_GB-alba-medium` #0) | en | CC-BY 4.0 | https://huggingface.co/datasets/rhasspy/piper-checkpoints |
| Joe (`en_US-joe-medium` #0) | en | CC0 | https://huggingface.co/datasets/rhasspy/piper-checkpoints |
| John (`en_US-john-medium` #0) | en | Domaine public | https://huggingface.co/datasets/rhasspy/piper-checkpoints |
| Sharvard (`es_ES-sharvard-medium` #1) | es | CC-BY 3.0 | https://datashare.ed.ac.uk/handle/10283/574 |
| DaveFX (`es_ES-davefx-medium` #0) | es | CC0 | https://github.com/OHF-Voice/voice-datasets |
| Claude (MX) (`es_MX-claude-high` #0) | es | Apache 2.0 | https://huggingface.co/datasets/rhasspy/piper-checkpoints |

Les modeles viennent de [piper-voices](https://huggingface.co/rhasspy/piper-voices)
et des publications de [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx).
Aucune voix sous licence non commerciale ou AGPL n'est distribuee ici.

## Contenu

- `<pack>.onnx` : le modele ;
- `<pack>.tokens.txt` : ses jetons ;
- `<pack>.<locuteur>.extrait.wav` : quelques secondes de la voix ;
- `espeak-ng-data.zip` : les donnees de prononciation, communes ;
- `manifest.json` : le catalogue que lit l'application.
