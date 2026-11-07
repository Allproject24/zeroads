import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import app

class FixPath:
    def __init__(self, app):
        self.app = app
    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path.startswith('/api/index'):
            path = path[len('/api/index'):] or '/'
            environ['PATH_INFO'] = path
        if path.startswith('/api'):
            # /api/bypass -> /bypass, biar route Flask ketemu
            environ['PATH_INFO'] = path[4:] or '/'
        return self.app(environ, start_response)

app = FixPath(app)
