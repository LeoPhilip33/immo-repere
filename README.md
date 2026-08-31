# Repère — lire une annonce immobilière

Outil pédagogique gratuit destiné à quelqu'un qui regarde une annonce immobilière pour la
première fois de sa vie. Il situe le prix au m² d'un bien parmi les ventes réellement signées
dans la même commune, puis chiffre ce que l'opération coûte selon le projet.

**Le livrable est un fichier unique : [`index.html`](index.html).** Tout est dedans — CSS,
JavaScript, données. Aucune requête réseau, aucun CDN, aucune police distante, aucune
bibliothèque. Il s'ouvre par double-clic sous Windows et macOS, en mode avion, et fonctionne
à l'identique.

| | |
|---|---|
| Poids | 1 271 Ko (cible : moins de 1 536 Ko) |
| Affichage de l'accueil | 163 ms |
| Communes et arrondissements | 35 011 |
| Ventes de référence retenues | 2 892 140 |
| Contrôles internes | 25, tous au vert |
| Requêtes réseau sortantes | aucune |

---

## La règle qui gouverne tout le reste

Toute valeur manipulée appartient à une de ces trois natures, et son traitement en découle.

| Nature | Traitement | Exemples |
|---|---|---|
| **DONNÉE** | Fait mesuré et publié. Affiché avec sa source et sa date. Jamais modifiable. | prix médians au m², taux moyens du marché, marges de négociation |
| **RÈGLE** | Barème ou mécanique de calcul. Calculé. Jamais sur un curseur. | frais de notaire, amortissement, impôt sur la plus-value, abattements |
| **HYPOTHÈSE** | Projection qui appartient à l'utilisateur. Curseur + champ éditable. Valeur de départ présentée comme « point de départ ». | loyer, taux de remplissage, prix par nuit, travaux, prix de revente |

Trois interdits, tenus dans le code :

1. jamais une RÈGLE sur un curseur ;
2. jamais une HYPOTHÈSE présentée comme une DONNÉE — chaque valeur par défaut porte la
   mention « Point de départ. Fais-le bouger. » ;
3. jamais un résultat affirmé sans rappeler l'hypothèse dont il dépend — formulation
   « Si tu supposes X, alors Y. »

Chaque constante de référence est étiquetée `DONNEE`, `REGLE` ou `HYPOTHESE` dans l'objet
`REF`, en tête du fichier, avec sa source et sa date.

---

## Refabriquer le fichier

Le fichier livré est engendré. La source est `preparation/modele.html` (le gabarit, sans
données) plus la chaîne de préparation.

```bash
cd preparation
./01_telecharger.sh      # ~300 Mo compressés, ~2 Go décompressés
./02_extraire.sh         # extraction + tri externe par mutation (~4 min)
python3 03_agreger.py    # filtrage, écrêtage, quantiles (~3 min)
python3 04_encoder.py    # encodage compact + injection -> ../index.html
node 05_controles_node.js  # rejoue les 25 contrôles hors navigateur
```

`preparation/data/` et `preparation/travail/` ne sont pas versionnés : ce sont des données
brutes retéléchargeables.

### Source et millésime

Demandes de valeurs foncières (DVF), DGFiP, diffusion Etalab sur data.gouv.fr.
**Millésime épinglé au 5 avril 2026** — les URL de `01_telecharger.sh` contiennent
l'horodatage `20260405`, ce qui garantit des chiffres reproductibles. Fenêtre de référence :
1ᵉʳ janvier 2024 au 31 décembre 2025. Prochaine publication annoncée : octobre 2026.

Licence Ouverte Etalab 2.0 : réutilisation commerciale autorisée avec mention de la source,
et interdiction de toute ré-identification. **Seuls des agrégats communaux sont embarqués** —
jamais une transaction, jamais une adresse, jamais une parcelle. Cette contrainte est
structurante, y compris « pour plus tard ».

### Filtrage, dans cet ordre

1. `nature_mutation = "Vente"` uniquement. Sont écartées les ventes en l'état futur
   d'achèvement, échanges, adjudications, expropriations et ventes de terrain à bâtir.
2. `type_local ∈ {Appartement, Maison}`.
3. **Exclusion des mutations portant sur plusieurs locaux d'habitation.** Une mutation DVF
   porte une valeur foncière unique pouvant couvrir plusieurs lots ; diviser ce total par la
   surface d'un seul lot gonfle le prix au m² de 10 à 30 %. C'est l'erreur numéro un sur ce
   jeu de données. **455 521 mutations ont été écartées à ce titre, soit 9,5 %.**
4. Valeur foncière nulle, absente ou inférieure à 10 000 €.
5. Surface nulle, absente, inférieure à 8 m² ou supérieure à 1 000 m².
6. `prix_m2 = valeur_fonciere / surface_reelle_bati`.
7. Écrêtage sous le 5ᵉ et au-dessus du 95ᵉ percentile, par couple (commune, type), avant
   tout agrégat.

### Agrégation

Cinq quantiles — p10, p25, p50, p75, p90 — et non trois. Les distributions de prix
immobiliers sont fortement asymétriques à droite : avec les seuls quartiles, tout prix
au-dessus de P75 obligerait à extrapoler avec une largeur inventée, ce qui saturerait la note
beaucoup trop vite et punirait un bien à peine au-dessus du marché.

- **Fenêtre adaptative** : 24 mois, puis 36, puis 48 si l'effectif reste sous 30. La fenêtre
  réellement utilisée est mémorisée et affichée à l'écran.
- **Maisons segmentées par surface de terrain** (moins ou plus de 500 m²) : le prix au m²
  habitable d'une maison est en grande partie un prix de terrain déguisé.
- **Paris, Lyon, Marseille agrégés par arrondissement.** Les communes globales 75056, 69123
  et 13055 sont absentes de la table.
- **Seuils d'effectif** : `n ≥ 30` normal · `10 ≤ n < 30` bandeau « peu de ventes
  comparables » · `n < 10` repli sur l'agrégat départemental, mention explicite.
- **Départements absents** du fichier national (livre foncier et non cadastre) : Moselle (57),
  Bas-Rhin (67), Haut-Rhin (68), Mayotte (976). Message honnête, jamais un « 0 €/m² » — et
  accès quand même au simulateur de crédit.

### Mesure faite sur le jeu de données

Rapport médian entre surface Carrez déclarée et surface réelle bâtie, appartements :
**1,0018 sur 822 312 lots.** L'écart est donc négligeable en pratique, contrairement à ce
qu'on lit souvent. Le chiffre est embarqué et affiché sur l'écran de verdict.

### Format d'embarquement

Table compacte parsée au chargement, index de recherche construit au chargement et non à la
frappe.

- noms triés, **préfixes partagés entre entrées consécutives** (1 signe en base 36 donne la
  longueur du préfixe repris) ;
- codes postaux et population en **base 36**, codes postaux secondaires en écart au premier ;
- quantiles en **blocs de 14 signes à largeur fixe, alphabet de 64 signes**, donc sans aucun
  séparateur : 1 signe type + fenêtre, 3 effectif, 2 p10, puis 4 × 2 signes d'écart au
  quantile précédent ;
- prix arrondis à 10 €/m² — la donnée d'entrée ne porte pas plus de précision ;
- les blocs d'effectif inférieur à 10 ne sont pas embarqués : ils basculent de toute façon
  sur l'agrégat départemental.

Table finale : 1 136 Ko pour 35 011 communes et 31 818 blocs de quantiles.

---

## Le biais de comparaison

Le prix saisi par l'utilisateur et le prix contenu dans DVF ne sont pas la même grandeur.
Trois écarts se cumulent, tous dans le même sens : DVF enregistre un **prix net vendeur**,
hors honoraires d'agence ; l'annonce est un **prix demandé**, avant négociation ; DVF mesure
la **surface réelle bâtie**, l'annonce la surface Carrez.

Sans correction, l'outil noterait tous les biens de France trop cher, d'une dizaine de points.
Un utilisateur qui connaît son marché verrait immédiatement que l'outil est faussé.

**On ne corrige pas en silence, on montre les deux.** Un curseur unique « Ce que tu verses
vraiment au vendeur » va du prix affiché vers le bas, avec deux repères fixes marqués sur la
barre : la marge de négociation moyenne de la ville et la part d'honoraires d'agence
généralement incluse. Le prix ainsi obtenu alimente le calcul du rang. Une correction
automatique et invisible transformerait une donnée en hypothèse déguisée ; un curseur
explicite garde l'hypothèse chez l'utilisateur.

---

## Barèmes embarqués

Tous regroupés dans l'objet `REF` en tête de fichier, chacun avec sa source et sa date, pour
que la mise à jour trimestrielle soit triviale. Vérifiés aux sources officielles au moment
d'écrire le code.

| Élément | Valeur | Source |
|---|---|---|
| Taux de crédit | 15 ans 3,33 % · 20 ans 3,44 % · 25 ans 3,52 % | Baromètre Pretto, août 2026 |
| Contrôle toutes durées | 3,30 % | Observatoire Crédit Logement / CSA, juillet 2026 |
| DMTO | 6,32 % courant · 5,81 % (11 départements et primo-accédants) · 5,09 % (Indre, Mayotte) | Article 1594 D du CGI, au 1ᵉʳ février 2026 |
| Émoluments du notaire | 3,870 % / 1,596 % / 1,064 % / 0,799 % par tranches, HT, TVA 20 % | Tarif réglementé |
| CSI | 0,10 %, minimum 15 € | — |
| Débours et formalités | forfait 1 200 €, affiché comme estimation | — |
| Marges de négociation | national −5,3 % · par ville | Observatoire Interkab, T1 2026 |
| Plus-value | IR 19 % · PS 17,2 % · abattements 150 U et suivants · surtaxe 1609 nonies G avec coefficients de lissage | CGI, BOFiP, Légifrance |
| Micro-foncier | abattement 30 %, plafond 15 000 €, PS 17,2 % | CGI art. 32 |
| Micro-BIC meublé | abattement 50 %, plafond **83 600 €**, PS **18,6 %** | Revalorisation triennale ; LFSS 2026 (loi n° 2025-1403) |
| Meublé de tourisme non classé | abattement 30 %, plafond 15 000 € | Loi Le Meur du 19 novembre 2024 |
| Repère HCSF | taux d'effort 35 % assurance comprise, durée 25 ans | Décision D-HCSF-2021-7 |

Le **régime réel n'est pas couvert** : un plan d'amortissement par composants calculé dans un
fichier hors ligne produirait des chiffres faux sur une déclaration. L'outil le dit et renvoie
vers un comptable.

Les coefficients de lissage de la surtaxe sont indispensables : sans eux, un euro de
plus-value supplémentaire coûterait des centaines d'euros d'impôt.

---

## Le moteur

Toutes les valeurs monétaires internes sont manipulées en **centimes entiers**. L'arrondi
n'intervient qu'à l'affichage.

- **Rang percentile** : interpolation linéaire par morceaux sur les cinq quantiles, chaque
  dénominateur testé — dans une petite commune, deux quantiles consécutifs peuvent être
  égaux. Plancher 2, plafond 98.
- **Mensualité** : convention française, taux proportionnel (`i = taux annuel / 12`), pas
  actuariel — c'est dit dans les limites.
- **Amortissement** : les intérêts se calculent chaque mois sur le capital restant dû, jamais
  sur le capital initial. La dernière échéance est ajustée pour que le capital restant dû
  final vaille exactement zéro.
- **Assurance emprunteur** : prime constante sur le capital initial, hors de l'amortissement —
  elle ne rembourse aucun capital. Les limites signalent que certains contrats la calculent
  sur le capital restant dû.
- **Phrase pédagogique sur les intérêts** : calculée, jamais écrite en dur. La part d'intérêts
  dans la première mensualité change complètement de sens selon la durée.
- **Cohérence de somme** : quand un écran affiche des postes et leur total, le total est
  calculé puis le résidu d'arrondi est répercuté sur le poste le plus élevé. La somme des
  postes affichés est toujours exactement égale au total affiché.
- **Formateur unique** : toute valeur non finie donne un tiret. Jamais de `NaN`, `Infinity`,
  `undefined` ni `-0 €` à l'écran.

---

## Contrôles internes

Accessibles depuis le pied de page. Les 25 vérifications tournent **dans le navigateur, sur le
code réellement chargé**, et chaque contrôle s'affiche en réussite ou en échec — l'outil ne
cache pas ses propres défauts. `preparation/05_controles_node.js` rejoue la même suite hors
navigateur, pour l'intégration continue.

Sont couverts : mensualité et amortissement de référence, frais d'acquisition calculés à
partir des composants, cohérence de somme sur 40 jeux tirés au hasard, départements exclus,
arrondissements, correction du biais de comparaison effectivement branchée, quantiles égaux et
divisions par zéro, robustesse sur toute la plage des curseurs aux deux extrémités,
vocabulaire interdit, absence de ressource extérieure, poids du fichier.

Deux contrôles cherchent des chaînes qui, écrites en clair, se trouveraient elles-mêmes dans
le fichier : leurs motifs sont assemblés morceau par morceau.

---

## Déploiement

Le site est statique : `index.html` est servi tel quel depuis la racine.
[`vercel.json`](vercel.json) fixe une Content-Security-Policy qui interdit toute connexion
sortante (`connect-src 'none'`) — la promesse « aucune donnée saisie n'est envoyée nulle part »
est ainsi tenue par le navigateur, pas seulement par le code.

---

Outil pédagogique gratuit. Ne constitue ni un conseil en investissement, ni une estimation
immobilière, ni une offre de crédit.
