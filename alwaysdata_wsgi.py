import os
import sys

# Ajouter le chemin du projet au PYTHONPATH
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.insert(0, path)

# Définir le répertoire de données pour les stockages persistants
os.environ['DATA_DIR'] = path

# Importer l'application Flask
from app import app as application
