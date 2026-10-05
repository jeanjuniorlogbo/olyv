"""Serveur de développement :  python server.py
Production (Linux) :  gunicorn -w 4 server:application   derrière un proxy HTTPS.
"""
import logging
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import config
from app import (routes_account, routes_admin, routes_auth, routes_doctor,   # noqa: F401
                 routes_facility, routes_pages, routes_patient)      # (enregistrent les routes)
from app.web import application

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')


class ThreadedServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class QuietHandler(WSGIRequestHandler):
    def log_message(self, fmt, *args):
        logging.getLogger('Olyvera.http').info(fmt, *args)


if __name__ == '__main__':
    with make_server(config.HOST, config.PORT, application,
                     server_class=ThreadedServer, handler_class=QuietHandler) as server:
        print(f'Olyvera : http://{config.HOST}:{config.PORT}')
        server.serve_forever()
