#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Étape 0 — veille sur les sources.

Interroge data.gouv.fr et compare le millésime DVF publié à celui embarqué dans
le fichier livré. Sert à deux choses :
  · en local, savoir en une commande s'il y a lieu de refabriquer ;
  · en intégration continue, décider s'il faut lancer la chaîne complète.

Vérifie aussi l'âge des barèmes saisis à la main. Ceux-là ne sont pas
automatisables — Pretto n'a pas d'API, Interkab publie en PDF, et les barèmes
fiscaux sont des textes de loi qui se lisent. Le script se contente donc de
rappeler quand il est temps d'aller les revoir, avec l'adresse de chacun.

Codes de sortie :
   0  rien à faire
  10  nouveau millésime DVF disponible
  20  millésime inchangé, mais des barèmes méritent une revue
  30  les deux
   1  erreur d'accès à la source
"""
import json, os, sys, urllib.request, urllib.error
from datetime import date

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)

# Jeu de données « Demandes de valeurs foncières » sur data.gouv.fr.
DATASET = "5c4ae55a634f4117716d5656"
API = "https://www.data.gouv.fr/api/1/datasets/%s/" % DATASET
ANNEES_VOULUES = 4          # fenêtre maximale de 48 mois


def lire_json(url, timeout=45):
    requete = urllib.request.Request(url, headers={
        "User-Agent": "repere-veille/1.0 (+https://github.com/LeoPhilip33/immo-repere)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(requete, timeout=timeout) as r:
        return json.load(r)


def ressources_dvf():
    """Renvoie {annee: {url, millesime}} pour les années les plus récentes."""
    d = lire_json(API)
    trouvees = {}
    for r in d.get("resources", []):
        titre = (r.get("title") or "").strip()
        if not titre.startswith("Valeurs foncières "):
            continue
        annee = titre.rsplit(" ", 1)[-1]
        if not (annee.isdigit() and len(annee) == 4):
            continue
        trouvees[int(annee)] = {
            "url": r.get("url"),
            # La date de dernière modification de la ressource EST le millésime :
            # DGFiP republie l'ensemble des années à chaque diffusion.
            "millesime": (r.get("last_modified") or "")[:10],
        }
    if not trouvees:
        raise RuntimeError("aucune ressource « Valeurs foncières » trouvée")
    recentes = sorted(trouvees)[-ANNEES_VOULUES:]
    return {a: trouvees[a] for a in recentes}


def millesime_embarque():
    """Le millésime réellement présent dans le fichier livré, pas celui qu'on
    croit y avoir mis."""
    chemin = os.path.join(ICI, "millesime.json")
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            return json.load(f).get("millesime")
    return None


def mois_ecoules(iso):
    a, m, _ = (int(x) for x in iso.split("-"))
    auj = date.today()
    return (auj.year - a) * 12 + (auj.month - m)


def main():
    sortie = {"verifie_le": date.today().isoformat()}
    code = 0

    # --- Millésime DVF ---
    try:
        res = ressources_dvf()
    except (urllib.error.URLError, OSError, RuntimeError, ValueError) as e:
        print("!! source inaccessible : %s" % e, file=sys.stderr)
        return 1

    publie = max(v["millesime"] for v in res.values())
    embarque = millesime_embarque()
    nouveau = bool(embarque) and publie > embarque

    sortie["dvf"] = {
        "publie": publie,
        "embarque": embarque,
        "nouveau": nouveau,
        "annees": sorted(res),
        "ressources": {str(a): res[a]["url"] for a in sorted(res)},
    }
    print("millésime DVF publié   : %s" % publie, file=sys.stderr)
    print("millésime DVF embarqué : %s" % (embarque or "(inconnu)"), file=sys.stderr)
    if nouveau:
        print("-> un nouveau millésime est disponible", file=sys.stderr)
        code += 10
    else:
        print("-> à jour", file=sys.stderr)

    # --- Âge des barèmes saisis à la main ---
    chemin_b = os.path.join(ICI, "baremes.json")
    a_revoir = []
    if os.path.exists(chemin_b):
        with open(chemin_b, encoding="utf-8") as f:
            baremes = json.load(f)
        for b in baremes.get("elements", []):
            age = mois_ecoules(b["verifie_le"])
            if age >= b.get("rythme_mois", 3):
                a_revoir.append({
                    "libelle": b["libelle"], "source": b["source"],
                    "url": b.get("url", ""), "verifie_le": b["verifie_le"],
                    "age_mois": age,
                })
    sortie["baremes_a_revoir"] = a_revoir
    if a_revoir:
        print("\nbarèmes à revoir :", file=sys.stderr)
        for b in a_revoir:
            print("  · %s — %s, vérifié il y a %d mois"
                  % (b["libelle"], b["source"], b["age_mois"]), file=sys.stderr)
        code += 20
    else:
        print("barèmes : aucun à revoir", file=sys.stderr)

    # La sortie standard porte le JSON, exploitable par l'intégration continue.
    json.dump(sortie, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return code


if __name__ == "__main__":
    sys.exit(main())
