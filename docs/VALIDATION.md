# Validation observée — 3 octobre 2026

## Résultats locaux

- **25 tests Python réussis** : distributions 4–0–0, 3–1–0, 2–1–1 et 2–2 ; réponses invalides ; annulation/remplacement ; scores attribués une seule fois ; reprise de phase/manche ; clôture ; PIN ; refus de vol d'équipe ; reconnexion ; confidentialité ; identifiants de phase périmés ; instantanés de reprise.
- Le test clavier parcourt **la vraie classe Application**, quatre manches et le score 5/5. Il vérifie la fin instantanée de frappe, le chrono facultatif, la pause, les confirmations et la sortie.
- F11 et le rendu ont été exercés avec SDL à **1920 × 1080, 1600 × 900 et 1366 × 768**. Ces tests vérifient le rendu local, pas la lisibilité depuis le fond d'un amphithéâtre.
- `scripts/simulate.py` a exécuté le **vrai transport PresenterNetwork de Pygame** avec quatre clients WebSocket sur TCP, un QR rendu, quatre manches, un départage, une reconnexion et une fermeture de salle. Scores : **[5, 5, 5, 0]**.
- Vérification browser initiale via **agent-browser** : page non vide, formulaire utilisable, aucune erreur navigateur détectée.
- `scripts/browser-check.cjs` a connecté **quatre vrais contextes Chromium** à l'application mobile. Largeurs 360, 390, 430 px ; sélection/verrouillage ; réouverture par l'animateur ; rechargement avec jeton de reprise ; analyses justes/fausses ; classement final avec égalité. Aucune erreur JavaScript/console et aucun débordement horizontal observé.
- Treize captures Pygame, un accueil QR et quatre captures mobile sont fournis dans `docs/screenshots/`. Toutes les branches ont été rendues pour vérifier l'absence d'exception.
- **EXE Windows construit et lancé**, avec fermeture automatique après 30 frames : code de sortie 0 et aucun message d'erreur dans le journal. Le JSON externe est fourni à côté de l'EXE.

## Corrections issues des essais

1. Une réouverture serveur doit enlever la réponse du cache local Pygame, même après un instantané de verrouillage déjà en file. La synchronisation retire maintenant les réponses absentes de l'instantané.
2. Le cache des polices est invalidé quand une nouvelle Application initialise SDL ; la création répétée dans les tests ne réutilise plus de polices après `pygame.quit()`.
3. Les flèches décoratives qui manquaient dans certaines polices ont été remplacées par un dessin vectoriel ou des symboles ASCII.
4. Les scores et les réponses des équipes sont montrés ensemble lors de la révélation d'analyse ; les points comptent brièvement vers leur valeur finale.
5. Les orbites ont été éclaircies et leur halo passe derrière les lignes pour conserver une silhouette continue.

## Limites

Ces résultats ne constituent pas un essai avec quatre téléphones physiques, un vrai projecteur, le Wi-Fi de la salle ou une répétition chronométrée devant public. Une courte répétition sur le matériel de présentation reste nécessaire.

La dépendance Starlette affiche actuellement un avertissement de dépréciation concernant httpx dans TestClient. Il n'affecte pas le résultat des tests ni le transport en production ; le simulateur TCP complète ces tests en mémoire.

Le statut des essais Railway et de l'arrêt du service est consigné séparément dans [RAILWAY.md](RAILWAY.md).

## Résultats hébergés

La simulation complète avec le vrai transport Pygame et quatre clients a été répétée sur le domaine Railway en **HTTPS/WSS**, avec le même score final [5, 5, 5, 0]. Les tests des quatre contextes Chromium ont également réussi sur le domaine public. Une inspection agent-browser de la page hébergée n'a détecté aucune erreur.

Après les tests, le déploiement actif a été retiré. L'API et l'interface Railway confirment l'absence de déploiement actif ; l'endpoint public renvoie HTTP 404. Aucune utilisation continue du backend de ce jeu n'est laissée active.
