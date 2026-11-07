import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import app

# FIX VERCEL: Vercel manggilnya /api/index, Flask maunya /
# Jadi kita belokin path nya balik ke aslinya
class FixPath:
    def __init__(self, app):
        self.app = app
    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path.startswith('/api/index'):
            path = path[len('/api/index'):] or '/'
            environ['PATH_INFO'] = path
        # Vercel juga kadang kirim path asli di header ini
        if 'HTTP_X_ORIGINAL_URL' in environ:
            pass
        return self.app(environ, start_response)

app = FixPath(app)
