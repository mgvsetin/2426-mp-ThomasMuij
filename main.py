import urllib.request
import urllib.response
import http.server

server = http.server.HTTPServer("127.0.0.1:8000")

class Server(http.server.HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, bind_and_activate = True):
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)
        server_port = 8000
        server_address = server_address
