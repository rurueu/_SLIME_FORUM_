MISE A JOUR DU SERVEUR RENDER

Remplace sur ton dépôt GitHub le server.py et requirements.txt par ceux de ce dossier,
puis laisse Render redéployer automatiquement.

Build Command :
pip install -r requirements.txt

Start Command :
gunicorn server:app

La base existante est mise à jour automatiquement avec la colonne parent_id.
