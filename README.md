# SimuJob - Simulateur d'Entretien d'Embauche

## Description du Projet

SimuJob est un simulateur d'entretien d'embauche interactif conçu pour aider les étudiants et les chercheurs d'emploi à se préparer efficacement aux entretiens d'embauche. Le système propose des questions adaptées à différents types de postes, analyse les réponses des utilisateurs en utilisant l'intelligence artificielle, et fournit un feedback personnalisé.

## Caractéristiques

- **Questions personnalisées** : Questions spécifiques à différents postes (Développeur Web, Data Scientist, etc.)
- **Analyse de sentiment** : Évaluation du ton et de la positivité des réponses
- **Feedback instantané** : Suggestions d'amélioration personnalisées basées sur l'analyse
- **Interface utilisateur intuitive** : Design moderne et responsive
- **Conseils professionnels** : Recommandations pour chaque type de poste
- **Sauvegarde des résultats** : Conservation des données pour suivi de la progression

## Technologies Utilisées

- **Backend** : Python avec Flask
- **Frontend** : HTML, CSS, JavaScript
- **Analyse de sentiment** : Hugging Face Transformers (DistilBERT)
- **Stockage de données** : Pandas avec Excel
- **Déploiement** : Local (développement)

## Structure du Projet

```
simulateur_entretien/
│
├── app.py                 # Application Flask principale
├── questions.xlsx         # Base de données des questions
├── requirements.txt       # Dépendances Python
├── README.md              # Documentation du projet
│
├── static/
│   └── style.css          # Styles CSS
│
├── templates/
│   ├── index.html         # Page d'accueil
│   ├── entretien.html     # Interface d'entretien
│   ├── resultat.html      # Page de résultats
│   └── conseils.html      # Conseils pour réussir les entretiens
│
└── resultats/             # Dossier pour sauvegarder les résultats des entretiens
```

## Installation

1. Clonez ce dépôt :
   ```bash
   git clone https://github.com/votre-nom/simulateur_entretien.git
   cd simulateur_entretien
   ```

2. Créez et activez un environnement virtuel :
   ```bash
   python -m venv venv
   source venv/bin/activate  # Sur Windows : venv\Scripts\activate
   ```

3. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

4. Lancez l'application :
   ```bash
   python app.py
   ```

5. Accédez à l'application dans votre navigateur à l'adresse : `http://127.0.0.1:5000`

## Utilisation

1. Sur la page d'accueil, remplissez vos informations et sélectionnez un type de poste
2. Répondez aux questions d'entretien simulées comme vous le feriez dans un entretien réel
3. Soumettez vos réponses pour recevoir une analyse détaillée
4. Consultez vos résultats et les conseils personnalisés
5. Recommencez pour vous entraîner davantage

## Capture d'écran

![Capture d'écran de l'application](screenshot_placeholder.png)

## Améliorations futures

- Intégration d'un système d'enregistrement audio/vidéo
- Analyse plus avancée (langage corporel, ton de voix)
- Création d'un tableau de bord pour suivre la progression
- Plus de types de postes et de questions
- Mode entraînement par catégories de questions
- Exportation des résultats en PDF

## Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## Contact

Pour toute question ou suggestion, contactez-moi à [votre-email@example.com].

---

**Projet de fin d'études en développement web - 2025**