import sys
import os

# Put pita/ on the path so Django can resolve its modules (pita.settings, etc.)
pita_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'pita')
sys.path.insert(0, pita_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pita.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
