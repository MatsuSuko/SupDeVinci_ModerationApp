# Application de Modération SupDeVinci

## Description
Application de modération développée dans le cadre du cours de M1 Développement Fullstack à SupDeVinci. Cette application permet de modérer du contenu en utilisant les services AWS.

## Auteurs
- Souvanny BOUNMY
- Léo LAFORE

## Structure du Projet
Le projet est divisé en trois parties (TP) :
- **TP1** : Script Python local pour la modération de contenu et notebook
- **TP2 & TP3** : Application web distante avec interface utilisateur

## Prérequis
- Python 3.x
- Compte AWS avec accès aux services suivants :
  - AWS S3
  - AWS Rekognition
- Variables d'environnement AWS configurées

## Installation

### Configuration locale
1. Clonez le repository :
```bash
git clone https://github.com/MatsuSuko/SupDeVinci_ModerationApp.git
cd SupDeVinci_ModerationApp
```

2. Créez un fichier `.env` à la racine du projet avec vos credentials AWS :
```env
ACCESS_KEY=votre_access_key
SECRET_KEY=votre_secret_key
```

### Dépendances
Installez les dépendances nécessaires :
```bash
pip install -r requirements.txt
```

## Utilisation

### TP1 - Script Local
Pour exécuter le script de modération local :
```bash
python3 code-finale.py
```

Pour tester d'autres fichiers :
1. Ouvrez le fichier `code-finale.py`
2. Modifiez le chemin du fichier dans la section "Configuration du fichier"

### TP2 & TP3 - Application Web
L'application est accessible à distance via :
```
http://52.47.209.112:8501
```

### Configuration du Bucket S3
Pour utiliser un bucket S3 différent :
1. Ouvrez le fichier `moderation.py`
2. Modifiez le nom du bucket dans la section "Configuration AWS"

## Structure des fichiers
```
SupDeVinci_ModerationApp/
├── assets         # Dossier contenant des fichiers images et vidéos pour les tests
├── 01-AWS_SocialMedia.ipynb         # Notebook du TP1
├── code-finale.py         # Script principal du TP1
├── app.py         # Application web des TP2 & TP3
├── moderation.py         # Application web des TP2 & TP3
├── .env                  # Fichier de configuration AWS
└── README.md            # Documentation
```

## Notes importantes
- Assurez-vous d'avoir correctement configuré vos credentials AWS dans le fichier `.env`
- Vérifiez les permissions de votre bucket S3
- L'application distante nécessite une connexion internet stable

## Licence
Ce projet est réalisé dans le cadre d'un cours à SupDeVinci.
