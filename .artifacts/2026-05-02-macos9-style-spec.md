# Spec: Mac OS 9 Style Interface for G3Bot

## Date
2026-05-02

## Summary
Transform G3Bot's interface from basic Mac OS 8.6 Platinum to refined Mac OS 9 Platinum style, with both question (prompt) and response fields using a dark terminal/console style (identical to current response field).

## Tasks

### Task 1: Style Mac OS 9 - index.html (page principale)
**Description**: Refaire le style de `templates/index.html` pour :
- Champ **Prompt** : transformer le `<textarea>` standard en terminal style avec fond `#111133`, texte `#55EE55`, police Monaco monospace, bordure `#666666`
- Boutons : style Platinum 3D avec relief (bordure blanche en haut/gauche, grise foncée en bas/droite)
- Gris de fond global : `#C0C0C0`
- Barres de titre : dégradé simulé `#CCCCCC` → `#BBBBBB`
- Polices : `Charcoal, Geneva, Chicago, Arial` pour labels, `Monaco, Courier` pour champs
- Panneaux avec `bgcolor="#EEEEEE"` et bordures décalées pour ombres
- Le select de modèle aussi en style Platinum

**Source files to read**:
- `templates/index.html`
- `app.py`

### Task 2: Style Mac OS 9 - models.html (page détails modèles)
**Description**: Refaire le style de `templates/models.html` pour cohérence Mac OS 9 :
- Même palette de couleurs et polices que index.html
- Tableau des modèles avec style Platinum (lignes alternées, en-tête gris)
- Boutons "Retour" et "Rafraîchir" en style Platinum 3D

**Source files to read**:
- `templates/models.html`
- `templates/index.html` (pour cohérence)

### Task 3: Style Mac OS 9 - wait.html (page de chargement)
**Description**: Refaire le style de `templates/wait.html` pour cohérence Mac OS 9 :
- Même palette et polices
- Barre de progression avec style Platinum (bordure 3D, fond blanc, remplissage bleu `#3366CC`)
- Centrage et espacement conformes au style Mac OS 9

**Source files to read**:
- `templates/wait.html`
- `templates/index.html` (pour cohérence)

## Shared Conventions
- HTML 4.01 Transitional uniquement
- Aucune CSS dans `<style>` ou fichiers `.css`
- Aucun JavaScript
- Utiliser exclusivement des `<table>`, `<font>`, attributs inline (`bgcolor`, `color`, `face`, `size`, `border`, `cellpadding`, `cellspacing`)
- Compatible Netscape 4 / Mac OS 8.6
- Pas d'emojis
- `nl2br` filter côté serveur pour les retours à la ligne
- Les boutons Platinum 3D se font via des tables imbriquées avec des couleurs de bordure différentes (blanc haut/gauche, gris foncé bas/droite)

## Review Criteria
1. **Compatibilité Netscape 4** : Aucune CSS, aucun JS, HTML pur avec tables et balises `<font>`
2. **Cohérence visuelle** : Les 3 pages partagent la même palette (fond #C0C0C0, panneaux #EEEEEE, terminal #111133)
3. **Champ prompt terminal** : Le textarea a fond sombre #111133 et texte vert #55EE55 en Monaco
4. **Boutons Platinum** : Relief 3D correctement simulé avec tables imbriquées et couleurs de bordure
5. **Pas de régression fonctionnelle** : Les formulaires POST/GET, les routes Flask, les variables Jinja2 restent inchangés
6. **Police monospace** : Monaco, Courier, monospace pour les champs terminal ; Charcoal, Geneva, Chicago pour le reste
7. **Aucun changement backend** : `app.py` n'est PAS modifié (uniquement les templates)
