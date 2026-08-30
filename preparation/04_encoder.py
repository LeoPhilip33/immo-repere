#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Étape 4 — encodage compact et fabrication du fichier livré.

Lit travail/agregats.json + data/communes.json, produit une table compacte,
l'injecte dans preparation/modele.html et écrit index.html à la racine.

Contraintes d'encodage :
  · base 36 partout pour les nombres ;
  · préfixes de noms partagés entre entrées consécutives (table triée par nom) ;
  · prix arrondis à 10 €/m² — la donnée d'entrée ne porte pas plus de précision ;
  · quantiles hauts stockés en écart au quantile précédent (petits nombres) ;
  · les blocs d'effectif inférieur à 10 ne sont pas embarqués : ils basculent
    de toute façon sur l'agrégat départemental.
"""
import json, os, sys

ICI = os.path.dirname(os.path.abspath(__file__))
TRV = os.path.join(ICI, "travail")
DATA = os.path.join(ICI, "data")
RACINE = os.path.dirname(ICI)

VERSION = "1.0.0"
DATE_PUBLICATION = "2026-08-30"
SEUIL_EMBARQUEMENT = 10          # en deçà, repli départemental
PAS_PRIX = 10                    # arrondi des prix au m², en euros
SEP_SECTION = "\n@\n"            # aucun nom de commune ne contient d'arobase

B36 = "0123456789abcdefghijklmnopqrstuvwxyz"
# Alphabet à 64 signes pour les blocs de quantiles : à largeur fixe, il permet
# de se passer de tout séparateur — le décodeur découpe par tranches.
B64 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_"
LARGEUR_BLOC = 14


def b36(n):
    """Entier positif -> base 36."""
    n = int(n)
    if n <= 0:
        return "0"
    s = ""
    while n:
        n, r = divmod(n, 36)
        s = B36[r] + s
    return s


def b64(n, largeur):
    """Entier positif -> base 64, sur un nombre fixe de signes."""
    n = int(n)
    if n < 0:
        n = 0
    plafond = 64 ** largeur
    if n >= plafond:
        # Mieux vaut échouer bruyamment qu'encoder une valeur fausse en
        # silence : un millésime futur qui déborderait doit se voir.
        raise ValueError("débordement d'encodage : %d ne tient pas sur %d signes"
                         % (n, largeur))
    s = ""
    for _ in range(largeur):
        n, r = divmod(n, 64)
        s = B64[r] + s
    return s


def encoder_bloc(typ, p):
    """Un bloc quantiles, sur exactement 14 signes et sans séparateur :
       1 signe  type de bien + fenêtre temporelle
       3 signes effectif
       2 signes p10 (en dizaines d'euros au m²)
       2 signes chacun : écart p25-p10, p50-p25, p75-p50, p90-p75
    Les quantiles hauts sont stockés en écart au quantile précédent : ce sont
    de petits nombres, alors que les quantiles eux-mêmes sont grands."""
    rang_type = {"A": 0, "M0": 1, "M1": 2}[typ]      # M0 petit terrain, M1 grand
    rang_fen = {24: 0, 36: 1, 48: 2}[p["mois"]]
    tete = B64[rang_type * 3 + rang_fen]
    q = [max(0, round(v / PAS_PRIX)) for v in p["q"]]
    # Les quantiles sont croissants par construction, mais deux quantiles
    # consécutifs peuvent être égaux dans une petite commune : l'écart vaut 0.
    ecarts = [max(0, q[i] - q[i - 1]) for i in range(1, 5)]
    bloc = tete + b64(p["n"], 3) + b64(q[0], 2) + "".join(b64(e, 2) for e in ecarts)
    assert len(bloc) == LARGEUR_BLOC
    return bloc


def prefixe_commun(a, b):
    n = min(len(a), len(b), 35)
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def main():
    agg = json.load(open(os.path.join(TRV, "agregats.json"), encoding="utf-8"))
    departements = json.load(open(os.path.join(DATA, "departements.json"), encoding="utf-8"))
    communes_ref = json.load(open(os.path.join(DATA, "communes.json"), encoding="utf-8"))
    arrm_ref = json.load(open(os.path.join(DATA, "arrondissements.json"), encoding="utf-8"))

    # Paris, Lyon et Marseille : on retire la commune globale et on la remplace
    # par ses arrondissements. Un prix médian « Paris » n'a aucun sens.
    GLOBALES = {"75056", "69123", "13055"}
    ref = [c for c in communes_ref if c["code"] not in GLOBALES] + arrm_ref
    ref.sort(key=lambda c: c["nom"])

    lignes = []
    precedent = ""
    n_blocs = 0
    for c in ref:
        nom = c["nom"]
        k = prefixe_commun(precedent, nom)
        precedent = nom

        cps = sorted({cp for cp in (c.get("codesPostaux") or []) if cp.isdigit()})
        if cps:
            base = int(cps[0])
            enc_cps = [b36(base)] + [b36(int(x) - base) for x in cps[1:]]
        else:
            enc_cps = []

        pop = b36(round((c.get("population") or 0) / 100))

        blocs = []
        for typ, p in sorted((agg["communes"].get(c["code"]) or {}).items()):
            if p["n"] >= SEUIL_EMBARQUEMENT:
                blocs.append(encoder_bloc(typ, p))
                n_blocs += 1

        # <préfixe><suffixe du nom> ; <insee sur 5><blocs de 14> ; <cp> ; <pop>
        lignes.append("%s%s;%s%s;%s;%s" % (
            B36[k], nom[k:], c["code"], "".join(blocs), ",".join(enc_cps), pop))

    section_communes = "\n".join(lignes)

    # Agrégats départementaux : filet de repli. À l'échelle d'un département
    # l'effectif est toujours largement suffisant.
    lignes_dep = []
    for dep, types in sorted(agg["departements"].items()):
        blocs = [encoder_bloc(t, p) for t, p in sorted(types.items())
                 if p["n"] >= SEUIL_EMBARQUEMENT]
        if blocs:
            lignes_dep.append("%s;%s" % (dep, "".join(blocs)))
    section_dep = "\n".join(lignes_dep)

    blob = section_communes + SEP_SECTION + section_dep

    print("communes encodées : %d · blocs : %d · blob : %.0f Ko"
          % (len(lignes), n_blocs, len(blob.encode("utf-8")) / 1024), file=sys.stderr)

    # --- injection dans le modèle ---
    modele = open(os.path.join(ICI, "modele.html"), encoding="utf-8").read()
    carrez = agg["carrez"]
    remplacements = {
        "__BLOB__": blob.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${"),
        "__CARREZ_RATIO__": "%.4f" % carrez["ratio_median"],
        "__CARREZ_LOTS__": str(carrez["lots"]),
        "__VENTES_RETENUES__": str(agg["stats"]["retenues"]),
        "__MUTATIONS_ECARTEES__": str(agg["stats"]["multi_lots"]),
        "__DEPARTEMENTS__": "|".join("%s:%s" % (d["code"], d["nom"])
                                     for d in sorted(departements, key=lambda x: x["code"])),
        "__VERSION__": VERSION,
        "__DATE_PUBLICATION__": DATE_PUBLICATION,
    }
    for cle, val in remplacements.items():
        if cle not in modele:
            print("!! marqueur absent du modèle : %s" % cle, file=sys.stderr)
        modele = modele.replace(cle, val)

    sortie = os.path.join(RACINE, "index.html")
    with open(sortie, "w", encoding="utf-8") as f:
        f.write(modele)
    print("-> %s (%.0f Ko)" % (sortie, os.path.getsize(sortie) / 1024), file=sys.stderr)


if __name__ == "__main__":
    main()
