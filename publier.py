#!/usr/bin/env python3
"""Fabrique et publie les voix WCL : modeles, extraits, manifeste.

CE QUE FAIT CE SCRIPT, ET POURQUOI IL EXISTE
--------------------------------------------
L'application ne peut pas embarquer les voix : une voix Piper pese 60 a 80 Mo,
neuf voix feraient 600 Mo dans le paquet du magasin. Elles sont donc SERVIES,
depuis la publication `v1` de ce depot, en fichiers PLATS :

    <pack>.onnx                 le modele
    <pack>.tokens.txt           ses jetons
    <pack>.<sid>.extrait.wav    quelques secondes a ecouter AVANT de telecharger
    espeak-ng-data.zip          les donnees de prononciation, communes a toutes
    manifest.json               le catalogue que lit l'application

Pas d'archive par voix : la phase 1 a mesure 37 s d'extraction bz2 sur un OPPO
d'entree de gamme, pour rien.

CE QUI EST VERIFIE, ET NON SUPPOSE
----------------------------------
- la licence : la ligne du MODEL_CARD amont est comparee a celle que le
  catalogue a enregistree. Si elle a change, on s'arrete. Une licence non
  commerciale (NC) ou AGPL arrete aussi la publication : l'application est
  payante ;
- le locuteur : `num_speakers` du modele doit contenir le `locuteur` declare.
  Un `sid` hors bornes donnerait une voix muette, ou quelqu'un d'autre ;
- le poids et l'empreinte SHA-256 : calcules sur le fichier publie, jamais
  recopies d'ailleurs. L'application refuse un modele dont l'empreinte ne
  correspond pas -- un telechargement tronque planterait le moteur au
  chargement, avec un message qui ne dirait pas pourquoi.

USAGE
-----
    python publier.py --verifier   # licences et locuteurs, sans rien telecharger
    python publier.py --preparer   # telecharge, extrait, rend les extraits, ecrit le manifeste
    python publier.py --publier    # + envoie tout dans la publication `v1` (gh)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent
SORTIE = RACINE / "sortie"
TRAVAIL = RACINE / "travail"

PIPER = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
SHERPA = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models"
ETIQUETTE = "v1"

# Ce qu'on refuse de distribuer dans une application payante.
INTERDITS = ("-nc-", "noncommercial", "non-commercial", "by-nc", "agpl")


def lire_catalogue() -> dict:
    return json.loads((RACINE / "catalogue.json").read_text(encoding="utf-8"))


def telecharger(url: str, cible: Path, essais: int = 4) -> Path:
    """Telecharge `url` vers `cible`, en reprenant les essais rates.

    Un fichier deja complet n'est pas retelecharge : sur un runner relance
    apres un pas rate, cela evite de recommencer 600 Mo.
    """
    if cible.exists() and cible.stat().st_size > 0:
        print(f"  deja la : {cible.name} ({cible.stat().st_size:,} o)")
        return cible
    cible.parent.mkdir(parents=True, exist_ok=True)
    derniere: Exception | None = None
    for essai in range(1, essais + 1):
        try:
            with urllib.request.urlopen(url, timeout=180) as rep, open(cible, "wb") as f:
                shutil.copyfileobj(rep, f, 1024 * 256)
            print(f"  recu    : {cible.name} ({cible.stat().st_size:,} o)")
            return cible
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            derniere = e
            print(f"  essai {essai}/{essais} echoue pour {url} : {e}")
            cible.unlink(missing_ok=True)
    raise RuntimeError(f"telechargement impossible : {url}") from derniere


def lire_texte(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as rep:
        return rep.read().decode("utf-8", "replace")


def verifier_pack(pack: dict) -> dict:
    """Licence et locuteurs, lus en amont. Rend la config du modele."""
    piper = pack["piper"]
    carte = lire_texte(f"{PIPER}/{piper}/MODEL_CARD")
    ligne = next(
        (l.strip() for l in carte.splitlines() if l.lower().startswith("* license")),
        "",
    )
    attendue = pack["licence_amont"].strip()
    if ligne != attendue:
        raise SystemExit(
            f"{pack['id']} : la licence amont a change.\n"
            f"  enregistree : {attendue}\n"
            f"  trouvee     : {ligne}\n"
            "  Relisez le MODEL_CARD avant de publier quoi que ce soit."
        )
    minuscule = ligne.lower()
    if any(mot in minuscule for mot in INTERDITS):
        raise SystemExit(f"{pack['id']} : licence non distribuable ({ligne}).")

    config = json.loads(lire_texte(f"{PIPER}/{piper}/{pack['id']}.onnx.json"))
    locuteurs = int(config.get("num_speakers", 1))
    for voix in pack["voix"]:
        if not 0 <= int(voix["locuteur"]) < locuteurs:
            raise SystemExit(
                f"{pack['id']} : locuteur {voix['locuteur']} hors bornes "
                f"({locuteurs} locuteur(s) dans le modele)."
            )
    noms = config.get("speaker_id_map") or {}
    print(
        f"  {pack['id']:24} {ligne[10:].strip():46} "
        f"{locuteurs} locuteur(s) {noms if noms else ''}"
    )
    return config


def extraire_pack(pack: dict) -> tuple[Path, Path]:
    """Descend l'archive sherpa-onnx et rend (modele, tokens)."""
    nom = f"vits-piper-{pack['id']}"
    archive = telecharger(f"{SHERPA}/{nom}.tar.bz2", TRAVAIL / f"{nom}.tar.bz2")
    dossier = TRAVAIL / nom
    if not dossier.exists():
        with tarfile.open(archive, "r:bz2") as tar:
            tar.extractall(TRAVAIL)
    modeles = sorted(dossier.glob("*.onnx"))
    if len(modeles) != 1:
        raise SystemExit(f"{pack['id']} : {len(modeles)} modele(s) dans l'archive.")
    tokens = dossier / "tokens.txt"
    if not tokens.exists():
        raise SystemExit(f"{pack['id']} : tokens.txt absent de l'archive.")
    return modeles[0], tokens


def empreinte(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloc)
    return h.hexdigest()


def zipper_espeak(source: Path) -> Path:
    """Les donnees de prononciation, une fois pour toutes les voix.

    Les chemins gardent le prefixe `espeak-ng-data/` : l'application decompresse
    l'archive dans son dossier `voix/` et attend le dossier a cet endroit.
    """
    cible = SORTIE / "espeak-ng-data.zip"
    if cible.exists():
        return cible
    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for fichier in sorted(source.rglob("*")):
            if fichier.is_file():
                z.write(fichier, f"espeak-ng-data/{fichier.relative_to(source)}")
    print(f"  espeak-ng-data.zip : {cible.stat().st_size:,} o")
    return cible


def rendre_extraits(
    pack: dict, modele: Path, tokens: Path, espeak: Path, textes: dict
) -> None:
    """Quelques secondes de chaque voix, rendues par le MEME moteur que l'app.

    Personne ne devrait recevoir 60 Mo pour decouvrir ensuite qu'il n'aime pas
    la voix.
    """
    import sherpa_onnx

    tts = sherpa_onnx.OfflineTts(
        sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=str(modele), tokens=str(tokens), data_dir=str(espeak)
                ),
                provider="cpu",
                num_threads=2,
                debug=False,
            ),
            max_num_sentences=1,
        )
    )
    for voix in pack["voix"]:
        cible = SORTIE / f"{pack['id']}.{voix['locuteur']}.extrait.wav"
        audio = tts.generate(
            textes[pack["langue"]], sid=int(voix["locuteur"]), speed=1.0
        )
        if len(audio.samples) == 0:
            raise SystemExit(f"{cible.name} : le moteur n'a rien produit.")
        sherpa_onnx.write_wave(str(cible), audio.samples, audio.sample_rate)
        secondes = len(audio.samples) / audio.sample_rate
        print(f"  extrait : {cible.name} ({secondes:.1f} s, {cible.stat().st_size:,} o)")


def ecrire_notes(catalogue: dict) -> Path:
    """Les notes de la publication : LA PAGE D'ATTRIBUTION.

    CC-BY oblige a citer l'origine partout ou l'on redistribue. C'est ici que
    cela se fait, et dans l'application, sous chaque voix. Les notes se
    reecrivent depuis le catalogue a chaque publication : deux listes qui
    divergent, c'est celle qu'on oublie qui devient fausse.
    """
    lignes = [
        "# Voix WCL - v1",
        "",
        "Les voix embarquees de l'application WCL Play : des modeles Piper",
        "(VITS), joues hors ligne par sherpa-onnx. Elles se telechargent depuis",
        "l'application, une par une, avec un extrait a ecouter avant.",
        "",
        "## Origine et licences",
        "",
        "| Voix | Langue | Licence | Jeu de donnees |",
        "| --- | --- | --- | --- |",
    ]
    for pack in catalogue["packs"]:
        for voix in pack["voix"]:
            lignes.append(
                f"| {voix['nom']} (`{pack['id']}` #{voix['locuteur']}) "
                f"| {pack['langue']} | {pack['licence']} | {pack['jeu_de_donnees']} |"
            )
    lignes += [
        "",
        "Les modeles viennent de [piper-voices](https://huggingface.co/rhasspy/piper-voices)",
        "et des publications de [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx).",
        "Aucune voix sous licence non commerciale ou AGPL n'est distribuee ici.",
        "",
        "## Contenu",
        "",
        "- `<pack>.onnx` : le modele ;",
        "- `<pack>.tokens.txt` : ses jetons ;",
        "- `<pack>.<locuteur>.extrait.wav` : quelques secondes de la voix ;",
        "- `espeak-ng-data.zip` : les donnees de prononciation, communes ;",
        "- `manifest.json` : le catalogue que lit l'application.",
        "",
    ]
    cible = RACINE / "NOTES_PUBLICATION.md"
    cible.write_text("\n".join(lignes), encoding="utf-8")
    return cible


def preparer(catalogue: dict, avec_extraits: bool = True) -> Path:
    SORTIE.mkdir(exist_ok=True)
    TRAVAIL.mkdir(exist_ok=True)
    espeak_zip: Path | None = None
    entrees: list[dict] = []

    for pack in catalogue["packs"]:
        print(f"\n{pack['id']}")
        config = verifier_pack(pack)
        modele, tokens = extraire_pack(pack)

        publie = SORTIE / f"{pack['id']}.onnx"
        if not publie.exists():
            shutil.copy2(modele, publie)
        shutil.copy2(tokens, SORTIE / f"{pack['id']}.tokens.txt")

        espeak = modele.parent / "espeak-ng-data"
        if not espeak.is_dir():
            raise SystemExit(f"{pack['id']} : espeak-ng-data absent de l'archive.")
        if espeak_zip is None:
            espeak_zip = zipper_espeak(espeak)
        if avec_extraits:
            rendre_extraits(pack, publie, tokens, espeak, catalogue["extraits"])

        octets = publie.stat().st_size
        sha = empreinte(publie)
        print(f"  modele  : {octets:,} o  sha256 {sha[:16]}...")
        for voix in pack["voix"]:
            entrees.append(
                {
                    "id": pack["id"],
                    "langue": pack["langue"],
                    "genre": voix["genre"],
                    "nom": voix["nom"],
                    "qualite": pack["qualite"],
                    "locuteur": int(voix["locuteur"]),
                    "octets": octets,
                    "sha256": sha,
                    "licence": pack["licence"],
                    "jeu_de_donnees": pack["jeu_de_donnees"],
                    "sample_rate": int(config["audio"]["sample_rate"]),
                }
            )

    ecrire_notes(catalogue)
    manifeste = SORTIE / "manifest.json"
    manifeste.write_text(
        json.dumps({"version": 1, "voix": entrees}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    total = sum(f.stat().st_size for f in SORTIE.iterdir() if f.is_file())
    print(
        f"\n{len(entrees)} voix, {len(catalogue['packs'])} paquets, "
        f"{total / 1048576:.0f} Mo a publier."
    )
    return manifeste


def publier() -> None:
    """Envoie le contenu de `sortie/` dans la publication `v1`.

    `--clobber` remplace les fichiers de meme nom : republier une voix corrigee
    ne demande pas de supprimer la publication, donc ne casse jamais les
    telechargements en cours.
    """
    fichiers = sorted(str(f) for f in SORTIE.iterdir() if f.is_file())
    if not fichiers:
        raise SystemExit("rien a publier : lancez d'abord --preparer.")
    vue = subprocess.run(
        ["gh", "release", "view", ETIQUETTE], capture_output=True, text=True
    )
    if vue.returncode != 0:
        subprocess.run(
            [
                "gh", "release", "create", ETIQUETTE,
                "--title", "Voix WCL - v1",
                "--notes-file", str(RACINE / "NOTES_PUBLICATION.md"),
            ],
            check=True,
        )
    subprocess.run(
        ["gh", "release", "upload", ETIQUETTE, *fichiers, "--clobber"], check=True
    )
    print(f"\nPublie : {len(fichiers)} fichiers dans {ETIQUETTE}.")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verifier", action="store_true", help="licences et locuteurs seulement")
    p.add_argument("--preparer", action="store_true", help="fabrique tout dans sortie/")
    p.add_argument("--publier", action="store_true", help="fabrique puis envoie")
    p.add_argument("--sans-extraits", action="store_true", help="saute la synthese")
    args = p.parse_args()
    if not (args.verifier or args.preparer or args.publier):
        p.print_help()
        return 2

    catalogue = lire_catalogue()
    if args.verifier:
        print("Licences et locuteurs, lus en amont :\n")
        for pack in catalogue["packs"]:
            verifier_pack(pack)
        print(f"\n{len(catalogue['packs'])} paquets verifies.")
        return 0

    preparer(catalogue, avec_extraits=not args.sans_extraits)
    if args.publier:
        publier()
    return 0


if __name__ == "__main__":
    sys.exit(main())
