#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Étape 3 — agrégation communale.

Entrée  : preparation/travail/mutations.tsv (trié par mutation, produit par 02).
Sortie  : preparation/travail/agregats.json

Ne sortent d'ici que des agrégats : effectifs et quantiles par commune et par
type de bien. Aucune transaction, aucune adresse, aucune parcelle. La Licence
Ouverte Etalab autorise la réutilisation commerciale avec mention de la source
et interdit toute ré-identification ; cette contrainte est structurante, y
compris « pour plus tard ».
"""
import json, os, sys
from collections import defaultdict

ICI = os.path.dirname(os.path.abspath(__file__))
TRV = os.path.join(ICI, "travail")

# --- Bornes de plausibilité (§2 du cahier des charges) ---
VALEUR_MIN_CENTS = 10_000 * 100   # cessions symboliques, ventes entre proches
SURFACE_MIN = 8                   # m²
SURFACE_MAX = 1000                # m²
SEUIL_TERRAIN = 500               # m² : segmentation des maisons

# --- Fenêtres temporelles, en mois glissants depuis 2022-01 ---
# La fenêtre de référence est 2024-01 -> 2025-12 (24 mois).
MOIS_FIN = 202512
FENETRES = [(24, 202401), (36, 202301), (48, 202201)]


def mois_index(ym: int) -> int:
    """AAAAMM -> index de mois depuis 2022-01, ou -1 hors plage."""
    a, m = divmod(ym, 100)
    i = (a - 2022) * 12 + (m - 1)
    return i if 0 <= i <= 47 else -1


def quantile(tri, q):
    """Quantile par interpolation linéaire sur une liste déjà triée."""
    n = len(tri)
    if n == 0:
        return None
    if n == 1:
        return float(tri[0])
    pos = q * (n - 1)
    bas = int(pos)
    haut = min(bas + 1, n - 1)
    frac = pos - bas
    return tri[bas] + (tri[haut] - tri[bas]) * frac


def ecreter(valeurs):
    """Écrêtage 5e / 95e percentile, appliqué avant tout autre agrégat.
    Les distributions de prix immobiliers ont une queue droite très longue :
    quelques ventes atypiques déplacent sensiblement les quantiles hauts."""
    tri = sorted(valeurs)
    if len(tri) < 3:
        return tri
    bas = quantile(tri, 0.05)
    haut = quantile(tri, 0.95)
    return [v for v in tri if bas <= v <= haut]


def profil(valeurs):
    """n + cinq quantiles, après écrêtage. Cinq et non trois : au-dessus de P75
    il faut sinon extrapoler avec une largeur inventée, ce qui sature la note
    beaucoup trop vite et punit un bien à peine au-dessus du marché."""
    v = ecreter(valeurs)
    n = len(v)
    if n == 0:
        return None
    return {
        "n": n,
        "q": [round(quantile(v, p)) for p in (0.10, 0.25, 0.50, 0.75, 0.90)],
    }


def main():
    src = os.path.join(TRV, "mutations.tsv")
    # groupes[(insee, type)] = liste de (index_mois, prix_m2_arrondi)
    groupes = defaultdict(list)
    dept_groupes = defaultdict(list)
    # Mesure du rapport Carrez / surface réelle bâtie, sur les appartements.
    ratios_carrez = []

    stats = {"mutations": 0, "retenues": 0, "multi_lots": 0,
             "hors_bornes": 0, "hors_fenetre": 0}

    def traiter(mut):
        """Décide du sort d'une mutation complète (toutes ses lignes)."""
        stats["mutations"] += 1
        # Locaux distincts, par nature. Les lignes répétées pour les parcelles
        # de terrain d'une même maison se replient sur la même sous-clé.
        habitations = {}
        autres_locaux = set()
        terrains = {}
        for insee, ym, cents, tl, bati, cz, terr, sl, st in mut:
            if tl in ("A", "M"):
                habitations[sl] = (insee, ym, cents, tl, bati, cz)
            elif tl == "C":
                autres_locaux.add(sl)
            if terr > 0:
                terrains[st] = terr

        # Filtre 3 — une mutation DVF porte une valeur foncière unique pouvant
        # couvrir plusieurs lots. Diviser ce total par la surface d'un seul lot
        # gonfle le prix au m² de 10 à 30 %. On écarte donc toute mutation qui
        # ne porte pas sur exactement un local d'habitation, et toute mutation
        # qui y adjoint un local commercial (même mécanique, même biais).
        if len(habitations) != 1 or autres_locaux:
            if habitations:
                stats["multi_lots"] += 1
            return
        insee, ym, cents, tl, bati, cz = next(iter(habitations.values()))

        # Filtres 4 et 5 — valeurs et surfaces implausibles.
        if cents < VALEUR_MIN_CENTS or not (SURFACE_MIN <= bati <= SURFACE_MAX):
            stats["hors_bornes"] += 1
            return

        mi = mois_index(ym)
        if mi < 0:
            stats["hors_fenetre"] += 1
            return

        # Filtre 6 — prix au m².
        prix_m2 = round(cents / 100 / bati)
        stats["retenues"] += 1

        if tl == "A":
            cle = "A"
            # Mesure embarquée : rapport Carrez déclarée / surface réelle bâtie.
            if cz > 0 and bati > 0:
                r = cz / bati
                if 0.3 <= r <= 1.3:      # au-delà, saisie manifestement erronée
                    ratios_carrez.append(r)
        else:
            # Le prix au m² habitable d'une maison est en grande partie un prix
            # de terrain déguisé : on segmente par surface de terrain.
            terrain = sum(terrains.values())
            cle = "M0" if terrain < SEUIL_TERRAIN else "M1"

        groupes[(insee, cle)].append((mi, prix_m2))
        dept = insee[:3] if insee[:2] == "97" else insee[:2]
        dept_groupes[(dept, cle)].append((mi, prix_m2))

    with open(src, encoding="utf-8") as f:
        courante = None
        tampon = []
        for ligne in f:
            c = ligne.rstrip("\n").split("\t")
            if len(c) < 10:
                continue
            mk = c[0]
            if mk != courante:
                if tampon:
                    traiter(tampon)
                courante = mk
                tampon = []
            tampon.append((c[1], int(c[2]), int(c[3]), c[4],
                           int(c[5]), float(c[6]), int(c[7]), c[8], c[9]))
        if tampon:
            traiter(tampon)

    print("mutations lues      :", stats["mutations"], file=sys.stderr)
    print("écartées multi-lots :", stats["multi_lots"], file=sys.stderr)
    print("écartées bornes     :", stats["hors_bornes"], file=sys.stderr)
    print("ventes retenues     :", stats["retenues"], file=sys.stderr)

    def agreger(source):
        """Fenêtre adaptative : 24 mois, puis 36, puis 48 si l'effectif reste
        sous 30. On mémorise la fenêtre réellement utilisée, elle est affichée."""
        out = {}
        for (cle_geo, typ), obs in source.items():
            retenu = None
            for duree, debut in FENETRES:
                seuil = mois_index(debut)
                vals = [p for (mi, p) in obs if mi >= seuil]
                p = profil(vals)
                if p is None:
                    continue
                retenu = {"n": p["n"], "q": p["q"], "mois": duree, "debut": debut}
                if p["n"] >= 30:
                    break
            if retenu:
                out.setdefault(cle_geo, {})[typ] = retenu
        return out

    communes = agreger(groupes)
    departements = agreger(dept_groupes)

    ratios_carrez.sort()
    carrez = {
        "ratio_median": round(quantile(ratios_carrez, 0.5), 4) if ratios_carrez else None,
        "lots": len(ratios_carrez),
    }
    print("ratio Carrez médian :", carrez, file=sys.stderr)

    os.makedirs(TRV, exist_ok=True)
    with open(os.path.join(TRV, "agregats.json"), "w", encoding="utf-8") as f:
        json.dump({"communes": communes, "departements": departements,
                   "carrez": carrez, "stats": stats}, f)
    print("-> travail/agregats.json", file=sys.stderr)


if __name__ == "__main__":
    main()
