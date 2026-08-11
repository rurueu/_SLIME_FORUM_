SLIME FORUM — MODÉRATION V2

Cette version serveur est nécessaire pour :
- corriger le 404 de suppression ;
- authentifier Créateur / Staff / Admin côté serveur ;
- supprimer des publications ;
- bannir une installation pendant 1 jour, 1 semaine, 1 mois, 1 an ou à vie ;
- afficher automatiquement le temps restant aux utilisateurs bannis.

À mettre sur le dépôt GitHub utilisé par ton service Render :
- server.py
- requirements.txt

Render :
Build Command :
pip install -r requirements.txt

Start Command :
gunicorn server:app

VARIABLE OBLIGATOIRE DANS RENDER :
Nom : SLIME_ADMIN_SECRET
Valeur : ton code personnel

Le code personnel n'est donc PAS écrit dans server.py ni dans client.py.

OPTION POUR LES MESSAGES PERSISTANTS :
Si tu utilises une base PostgreSQL, ajoute aussi DATABASE_URL dans Render.
Sinon le serveur utilise forum.db en SQLite.

IMPORTANT POUR LES BANS :
Les anciens messages créés avant cette mise à jour n'ont pas forcément d'identifiant
d'installation associé. Un bannissement par message fonctionnera pour les nouvelles
publications envoyées avec les nouveaux clients.

HIÉRARCHIE DE MODÉRATION :
- Créateur : peut supprimer/bannir utilisateurs, Staff et Admin.
- Staff/Admin : peuvent modérer les utilisateurs ordinaires.
- Staff/Admin : ne peuvent pas supprimer ou bannir le Créateur.


CORRECTION AUTHENTIFICATION :
- Le code personnel fonctionne maintenant même si SLIME_ADMIN_SECRET n'est pas configuré.
- Le mot de passe n'est pas écrit en clair dans server.py.
- Seule son empreinte SHA-256 est stockée comme secours.
- Si SLIME_ADMIN_SECRET existe dans Render, elle reste prioritaire.
