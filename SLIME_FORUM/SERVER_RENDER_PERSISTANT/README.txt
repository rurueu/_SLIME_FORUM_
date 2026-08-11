SLIME FORUM - SERVEUR AVEC MESSAGES PERSISTANTS

Ce dossier est prévu pour ton service Render.

Il utilise :
- PostgreSQL si la variable DATABASE_URL existe.
- SQLite seulement en secours/test local.

Avec PostgreSQL, les publications ne dépendent plus du disque temporaire du Web Service Render.

Sur Render :
Build Command :
pip install -r requirements.txt

Start Command :
gunicorn server:app

Ajoute ensuite la variable d'environnement DATABASE_URL contenant l'URL de ta base PostgreSQL.

Le serveur essaie aussi d'importer forum.db vers PostgreSQL si :
- forum.db existe encore au moment du premier démarrage ;
- la nouvelle base PostgreSQL est vide.

IMPORTANT :
aucun hébergeur ne peut promettre une conservation littéralement éternelle.
Une base persistante empêche surtout les messages de disparaître lors des redémarrages et redéploiements du Web Service.
