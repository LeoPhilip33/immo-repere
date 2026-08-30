#!/usr/bin/env bash
# Télécharge les sources brutes. Rien de tout cela n'est versionné ni embarqué :
# seuls les agrégats communaux produits par les étapes suivantes le sont.
#
# Source : Demandes de valeurs foncières (DVF), DGFiP, diffusion Etalab sur data.gouv.fr.
# Millésime épinglé : 5 avril 2026 (les URL contiennent l'horodatage 20260405).
# Licence Ouverte Etalab 2.0.
set -euo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"
DEST="$ICI/data"
mkdir -p "$DEST"

# Quatre millésimes annuels : la fenêtre de référence est de 24 mois (2024-2025),
# élargissable à 36 puis 48 mois pour les communes à faible effectif.
declare -a SRC=(
  "2022 https://static.data.gouv.fr/resources/demandes-de-valeurs-foncieres/20260405-002236/valeursfoncieres-2022.txt.zip"
  "2023 https://static.data.gouv.fr/resources/demandes-de-valeurs-foncieres/20260405-002251/valeursfoncieres-2023.txt.zip"
  "2024 https://static.data.gouv.fr/resources/demandes-de-valeurs-foncieres/20260405-002306/valeursfoncieres-2024.txt.zip"
  "2025 https://static.data.gouv.fr/resources/demandes-de-valeurs-foncieres/20260405-002321/valeursfoncieres-2025.txt.zip"
)
for ligne in "${SRC[@]}"; do
  set -- $ligne; an="$1"; url="$2"
  if [ ! -f "$DEST/ValeursFoncieres-$an.txt" ]; then
    echo "-> DVF $an"
    curl -sS -L -o "$DEST/dvf-$an.zip" "$url"
    unzip -o -q "$DEST/dvf-$an.zip" -d "$DEST"
    rm -f "$DEST/dvf-$an.zip"
  fi
done

# Référentiel des communes : nom, code INSEE, codes postaux, population.
# Source : API Géo (Etalab), assise sur le Code officiel géographique de l'INSEE.
echo "-> référentiel communes"
curl -sS "https://geo.api.gouv.fr/communes?fields=nom,code,codesPostaux,population,codeDepartement&format=json" -o "$DEST/communes.json"
# Arrondissements municipaux de Paris, Lyon et Marseille : jamais d'agrégat global
# pour ces trois villes, on descend systématiquement à l'arrondissement.
curl -sS "https://geo.api.gouv.fr/communes?type=arrondissement-municipal&fields=nom,code,codesPostaux,population,codeDepartement&format=json" -o "$DEST/arrondissements.json"
echo "OK"
curl -sS "https://geo.api.gouv.fr/departements?fields=code,nom" -o "$DEST/departements.json"
