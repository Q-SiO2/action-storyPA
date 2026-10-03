# Plan annoté — Palo Alto / Les signaux faibles

## Lecture et arbitrages

Les trois documents joints sont des versions successives. Le document 2 remplace les quatre choix du document 1 par **trois choix A/B/C**, fixe **quatre manches**, diversifie les analyses et porte la dernière récompense à **deux points**. Le document 3 ajoute les téléphones et Railway. Le mode manuel du document 1 reste obligatoire. Maximum : cinq points. Aucun point pour le dialogue.

Le dossier voisin `paloalto-live` a été inspecté : il s'agit d'une application Node/React/ONLYOFFICE avec identification individuelle, distincte de ce jeu. Aucun moteur Pygame existant dans le dossier demandé. Ce projet est créé séparément afin de préserver cette application.

## Séquence de réalisation

1. Scénario continu : Nora, Adam et Lina préparent un exposé. Détection → interprétation → classification → diagnostic. Trois branches courtes rejoignent chaque scène suivante.
2. Moteur déterministe : phases explicites, votes secrets, départage limité aux choix ex æquo, journal de saisie, score attribué une seule fois, reprise de manche.
3. Direction artistique : surface logique 1600 × 900 mise à l'échelle, marges généreuses, police de titre sobre et police terminal, signal orbital dessiné localement, panneaux translucides, typographie contrastée. Pas de ressources réseau pour le projecteur.
4. Réseau : un FastAPI, quatre contrôleurs, secrets de reconnexion, identifiant de phase renouvelé, instantanés adaptés au rôle. Le projecteur possède le scénario et les scores. Le serveur transporte et valide les réponses.
5. Mobile : HTML/CSS/JS locaux, grandes zones tactiles, sélection puis verrouillage, attente orientée vers l'écran principal, reconnexion.
6. Validation : moteur, autorisation et confidentialité, WebSockets réels, partie complète à quatre clients, captures de chaque écran majeur, résolutions et mode manuel.
7. Livraison : guide français, scripts Windows, EXE, Docker/Railway, essais hébergés si accès disponible puis arrêt du seul service de ce jeu.

## Contraintes annotées

| Exigence | Réalisation prévue |
|---|---|
| Quatre équipes / trois répliques | Validation du scénario et des sessions |
| Choix cachés | Public : statut uniquement ; animateur : réponses internes ; mobile : propre réponse |
| Analyse variable par branche | Objet `analysis` de chaque choix dans JSON |
| Saisie 1–4 puis chiffre | Deux frappes avec indicateur « équipe / réponse » pour éviter l'ambiguïté |
| Continuité sans Internet | F4 conserve les réponses déjà reçues ; ignore les paquets tardifs |
| Reprise en ligne | Seulement accueil ou transition ; nouvel identifiant de phase |
| Retour arrière / reprise | Retour arrière avant révélation ; menus confirmés pour les resets |
| Projecteur lisible | Texte ≥ 28 px sur la surface logique ; auto-retour à la ligne |
| Aucun secret projeté | F2 ne montre jamais la bonne réponse |
| Coûts Railway | Aucun DB/worker ; une instance ; arrêt vérifié après essais |

## Critères de fin

Une partie manuelle et une partie WebSocket parcourent les quatre manches ; scores et transitions restent cohérents ; les téléphones ne connaissent pas les réponses des autres avant révélation ; le guide indique clairement les résultats réellement vérifiés et les limites des essais physiques/hébergés.

## Réalisation vérifiée

Les sept étapes sont réalisées. Les résultats détaillés et corrections figurent dans [VALIDATION.md](VALIDATION.md). Les tests locaux et hébergés ont réussi ; l'EXE Windows a été construit et lancé. Les captures montrent les écrans réels. Le service Railway dédié est conservé mais son déploiement actif a été retiré après validation, car le connecteur refusait zéro réplique ; voir [RAILWAY.md](RAILWAY.md).
