#!/usr/bin/env bash
# Étape 1 — téléchargement des sources brutes.
#
# Rien de ce qui est téléchargé ici n'est versionné ni embarqué : seuls les
# agrégats communaux produits par les étapes suivantes le sont.
#
# Source : Demandes de valeurs foncières (DVF), DGFiP, diffusion Etalab sur
# data.gouv.fr. Licence Ouverte Etalab 2.0.
#
# Par défaut, le millésime est ÉPINGLÉ : les URL sont lues dans millesime.json
# et contiennent l'horodatage de la diffusion, si bien que la chaîne rebâtit
# exactement les mêmes chiffres, aujourd'hui comme dans deux ans.
#
#   ./01_telecharger.sh              millésime épinglé (reproductible)
#   ./01_telecharger.sh --dernier    interroge data.gouv.fr, prend le plus
#                                    récent et réécrit millesime.json
#
# L'intégration continue utilise --dernier ; un humain qui veut reproduire un
# build ne l'utilise pas.
set -euo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"
DEST="$ICI/data"
mkdir -p "$DEST"

if [ "${1:-}" = "--dernier" ]; then
  echo "-> interrogation de data.gouv.fr pour le dernier millésime" >&2
  python3 - "$ICI" <<'PY'
import json, os, sys
sys.path.insert(0, sys.argv[1])
import importlib.util
spec = importlib.util.spec_from_file_location(
    "veille", os.path.join(sys.argv[1], "00_verifier_sources.py"))
veille = importlib.util.module_from_spec(spec)
spec.loader.exec_module(veille)

res = veille.ressources_dvf()
millesime = max(v["millesime"] for v in res.values())
chemin = os.path.join(sys.argv[1], "millesime.json")
with open(chemin, encoding="utf-8") as f:
    actuel = json.load(f)
actuel["millesime"] = millesime
actuel["ressources"] = {str(a): res[a]["url"] for a in sorted(res)}
with open(chemin, "w", encoding="utf-8") as f:
    json.dump(actuel, f, ensure_ascii=False, indent=2)
    f.write("\n")
print("millesime.json mis à jour : %s" % millesime, file=sys.stderr)
PY
fi

# Les années à télécharger sont celles listées dans millesime.json : la fenêtre
# maximale de comparaison est de 48 mois, soit quatre millésimes annuels.
ANNEES=$(python3 -c "
import json,sys
d=json.load(open('$ICI/millesime.json'))
print(' '.join(sorted(d['ressources'])))
")
MILLESIME=$(python3 -c "
import json;print(json.load(open('$ICI/millesime.json'))['millesime'])")
echo "-> millésime : $MILLESIME (années : $ANNEES)" >&2

# Les fichiers déjà décompressés sont conservés d'une exécution à l'autre :
# 2 Go de texte, autant ne pas les retélécharger pour rien.
for an in $ANNEES; do
  if [ -f "$DEST/ValeursFoncieres-$an.txt" ]; then
    echo "   $an déjà présent" >&2
    continue
  fi
  url=$(python3 -c "
import json;print(json.load(open('$ICI/millesime.json'))['ressources']['$an'])")
  echo "-> DVF $an" >&2
  curl -sSf -L --retry 3 --retry-delay 5 -o "$DEST/dvf-$an.zip" "$url"
  unzip -o -q "$DEST/dvf-$an.zip" -d "$DEST"
  rm -f "$DEST/dvf-$an.zip"
  # DGFiP nomme parfois le fichier différemment de l'archive : on normalise.
  if [ ! -f "$DEST/ValeursFoncieres-$an.txt" ]; then
    trouve=$(ls "$DEST" | grep -iE "valeursfoncieres-$an\.txt$" | head -1 || true)
    [ -n "$trouve" ] && mv "$DEST/$trouve" "$DEST/ValeursFoncieres-$an.txt"
  fi
  [ -f "$DEST/ValeursFoncieres-$an.txt" ] || { echo "!! fichier $an introuvable après décompression" >&2; exit 1; }
done

# Référentiel des communes : nom, code INSEE, codes postaux, population.
# Source : API Géo (Etalab), assise sur le Code officiel géographique de l'INSEE.
echo "-> référentiel communes" >&2
curl -sSf --retry 3 "https://geo.api.gouv.fr/communes?fields=nom,code,codesPostaux,population,codeDepartement&format=json" -o "$DEST/communes.json"
# Arrondissements municipaux de Paris, Lyon et Marseille : jamais d'agrégat
# global pour ces trois villes, on descend systématiquement à l'arrondissement.
curl -sSf --retry 3 "https://geo.api.gouv.fr/communes?type=arrondissement-municipal&fields=nom,code,codesPostaux,population,codeDepartement&format=json" -o "$DEST/arrondissements.json"
curl -sSf --retry 3 "https://geo.api.gouv.fr/departements?fields=code,nom" -o "$DEST/departements.json"

# Contrôle de non-vacuité : un JSON tronqué casserait la suite en silence.
python3 - "$DEST" <<'PY'
import json, sys, os
for nom, mini in (("communes.json", 30000), ("arrondissements.json", 40), ("departements.json", 90)):
    d = json.load(open(os.path.join(sys.argv[1], nom), encoding="utf-8"))
    if len(d) < mini:
        raise SystemExit("!! %s ne contient que %d entrées" % (nom, len(d)))
    print("   %s : %d entrées" % (nom, len(d)), file=sys.stderr)
PY
echo "OK" >&2
