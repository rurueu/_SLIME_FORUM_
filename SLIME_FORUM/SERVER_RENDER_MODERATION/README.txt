Les fonctions Supprimer et Bannir nécessitent cette mise à jour serveur.
Le bannissement utilise un identifiant aléatoire d'installation, pas les numéros de série matériels.
Remplace server.py et requirements.txt sur le dépôt Render puis redéploie.
Build: pip install -r requirements.txt
Start: gunicorn server:app
