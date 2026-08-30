#!/usr/bin/env bash
# Étape 2 — extraction et tri par mutation.
#
# Le fichier DVF brut est à plat : une ligne par (disposition, lot ou parcelle).
# Une même mutation — un seul acte, une seule valeur foncière — occupe donc
# plusieurs lignes. Or la valeur foncière est portée à l'identique sur chacune.
# Diviser ce total par la surface d'un seul lot gonfle le prix au m² de 10 à 30 % :
# c'est l'erreur numéro un sur ce jeu de données.
#
# On regroupe donc physiquement les lignes par mutation (tri externe, mémoire
# constante) pour que l'étape 3 puisse décider, mutation par mutation, si elle
# porte sur un local d'habitation unique.
#
# Clé de mutation : département + date + n° de disposition + valeur foncière.
# Le département est inclus plutôt que la commune : une mutation peut porter sur
# plusieurs communes, et la scinder recréerait exactement le biais qu'on corrige.
set -euo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"
SRC="$ICI/data"; TRV="$ICI/travail"
mkdir -p "$TRV"

: > "$TRV/lignes.tsv"
for f in "$SRC"/ValeursFoncieres-*.txt; do
  echo "-> $(basename "$f")" >&2
  # Colonnes DVF utilisées :
  #  8 No disposition · 9 Date mutation · 10 Nature mutation · 11 Valeur fonciere
  # 19 Code departement · 20 Code commune · 21 Prefixe de section · 22 Section
  # 23 No plan · 25 1er lot · 26,28,30,32,34 Surfaces Carrez des 5 lots
  # 37 Type local · 39 Surface reelle bati · 40 Nombre pieces · 41 Nature culture
  # 43 Surface terrain
  LC_ALL=C awk -F'|' '
    NR == 1 { next }
    # Filtre 1 — ventes ordinaires uniquement. Sont écartées les ventes en
    # l état futur d achèvement, échanges, adjudications, expropriations et
    # ventes de terrain à bâtir : prix non comparables à celui d une annonce.
    $10 != "Vente" { next }
    {
      dep = $19; com = $20
      # Code INSEE : le département tient sur 2 caractères en métropole
      # et 3 en outre-mer ; la commune complète à 5.
      if (length(dep) == 3) insee = dep sprintf("%02d", com + 0)
      else insee = dep sprintf("%03d", com + 0)

      val = $11; gsub(/,/, ".", val)
      cents = sprintf("%.0f", val * 100)
      if (cents + 0 <= 0) next

      # Date au format JJ/MM/AAAA -> AAAAMM
      ym = substr($9, 7, 4) substr($9, 4, 2)

      # A appartement · M maison · C local commercial ou industriel
      # D dépendance ou autre local · "-" ligne sans local (parcelle seule)
      tl = "-"
      if ($37 == "Appartement") tl = "A"
      else if ($37 == "Maison") tl = "M"
      else if (substr($37, 1, 5) == "Local") tl = "C"
      else if ($37 != "") tl = "D"

      bati = $39 + 0
      terr = $43 + 0

      # Surface Carrez : somme des cinq lots éventuels de la ligne.
      cz = 0
      for (i = 26; i <= 34; i += 2) { c = $i; gsub(/,/, ".", c); cz += c + 0 }

      # Sous-clé d unicité d un local à l intérieur de la mutation :
      # parcelle + lot + nature + surface. Les lignes répétées pour les
      # parcelles de terrain d une même maison se replient dessus.
      sub_local = $21 "/" $22 "/" $23 "/" $25 "/" $37 "/" bati "/" $40
      # Sous-clé d unicité d une parcelle, pour ne pas compter deux fois
      # le même terrain décliné en plusieurs natures de culture.
      sub_terr = $21 "/" $22 "/" $23 "/" $41

      printf "%s~%s~%s~%s\t%s\t%s\t%s\t%s\t%d\t%.2f\t%d\t%s\t%s\n", \
        dep, $9, $8, cents, insee, ym, cents, tl, bati, cz, terr, sub_local, sub_terr
    }
  ' "$f" >> "$TRV/lignes.tsv"
done

echo "-> tri par mutation" >&2
LC_ALL=C sort -S 1G -T "$TRV" -t $'\t' -k1,1 "$TRV/lignes.tsv" -o "$TRV/mutations.tsv"
rm -f "$TRV/lignes.tsv"
wc -l "$TRV/mutations.tsv"
