# Audio et mouvement

La couche de feedback accompagne la simulation sans changer les votes, les branches ou les points. Les assets sont locaux, inclus dans l'EXE et disponibles sans Internet.

## Sources recherchées et retenues

Les pages officielles de Kenney indiquent **CC0** pour [Voiceover Pack](https://kenney.nl/assets/voiceover-pack), [Interface Sounds](https://kenney.nl/assets/interface-sounds) et [Digital Audio](https://kenney.nl/assets/digital-audio). Les deux premiers packs ont été retenus : leurs signaux courts conviennent mieux à une présentation que les lasers du troisième. Les textes de licence originaux sont conservés dans `assets/audio`.

Téléchargements originaux :

- [Voiceover Pack ZIP](https://kenney.nl/media/pages/assets/voiceover-pack/3f7f168698-1677589897/kenney_voiceover-pack.zip)
- [Interface Sounds ZIP](https://kenney.nl/media/pages/assets/interface-sounds/fa43c1dd4d-1677589452/kenney_interface-sounds.zip)

| Fichier livré | Enregistrement original | Déclenchement |
|---|---|---|
| `select.wav` | `Audio/select_001.ogg` | sélection d'équipe |
| `lock.wav` | `Audio/confirmation_002.ogg` | nouvelle réponse reçue |
| `reopen.wav` | `Audio/back_001.ogg` | réponse rouverte |
| `transition.wav` | `Audio/maximize_001.ogg` | changement de phase |
| `reveal.wav` | `Audio/glass_001.ogg` | révélation publique / classement |
| `voice_ready.wav` | `Female/ready.ogg` | accueil validé |
| `voice_final_round.wav` | `Female/final_round.ogg` | début de la dernière manche |
| `voice_complete.wav` | `Female/mission_completed.ogg` | classement final |

Les trois annonces système sont **en anglais**, très courtes. Le scénario, les dialogues et l'interface restent en français. Il s'agit de voix enregistrées sous CC0, légèrement traitées comme un canal radio : modulation discrète, filtrage léger, écho de 55 ms et enveloppe anti-clic. Aucun clonage de voix ni service de synthèse en ligne. `scripts/prepare_audio.py` reproduit les fichiers à partir des archives extraites dans `.audio-source/voice` et `.audio-source/interface`.

## Présentateur

- **M** active/coupe tous les sons ; `--mute` démarre silencieusement.
- **F3** désactive les mouvements ; `--reduced-motion` démarre avec les animations désactivées et le texte immédiatement lisible.
- Deux canaux séparés pour voix et effets. Une annonce précédente s'arrête au changement de phase. Pause, aide et menus suspendent l'audio et le temps des mouvements.
- Hop de sélection de 9 px, confirmation de 5 px, secousse de réouverture de 3 px. Durée maximale 420 ms.
- Transition numérique de 420 ms : paquets fins et segments sur les bords du contenu, sans flash plein écran. Le texte reste lisible.
- Un défaut de périphérique audio laisse le jeu fonctionner silencieusement.
- La confirmation utilise uniquement la réception d'une réponse. Elle ne dépend jamais du choix A/B/C ou de sa justesse. Aucun vote secret n'est révélé par un son ou une animation.

## Téléphones

- **SON / OFF** par défaut ; activation explicite par le joueur. Les petits pips sont synthétisés par Web Audio, sans téléchargement supplémentaire ni voix simultanées sur quatre téléphones.
- Hop de carte de 6 px, pression de bouton de 2 px, entrée numérique, compteur et classement animés.
- Vibration courte à la sélection et après confirmation du serveur, uniquement lorsque l'API du navigateur est disponible. Les navigateurs/appareils sans vibration continuent normalement.
- **EFFETS / CALME** et préférence système `prefers-reduced-motion` désactivent animations et vibration. Le choix local est conservé. La préférence système reste prioritaire.
- Les instantanés inchangés, battements réseau et verrouillages des autres équipes ne reconstruisent plus l'écran : pas de boucle d'animation, de saut de focus ou de sons répétés.

## Vérification

Tests dédiés : mêmes cues pour les trois réponses secrètes, une seule confirmation par événement, réouverture sans écraser la secousse, absence de répétition lors des instantanés, horloge suspendue en pause, WAV valides et courts, mute immédiat, panne audio facultative.

Les tests Chromium vérifient l'activation réelle d'AudioContext, l'animation de sélection, le focus conservé après un instantané répété et la préférence de mouvement réduit. Les appels à la vibration sont enregistrés avec un périphérique simulé ; la vibration physique et le volume des enceintes doivent être vérifiés sur le matériel de présentation.
