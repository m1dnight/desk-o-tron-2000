from tornado.httpserver import HTTPServer
from tornado.web import StaticFileHandler, Application
from tornado.websocket import WebSocketHandler


class DeskSocketHandler(WebSocketHandler):
    callback = None
    hostname = None
    this = None
    connections = set()
    
    def check_origin(self, origin):
        print(origin)
        print(self.hostname)
        origin == self.hostname

    def initialize(self, callback, hostname):
        self.this = self
        self.callback = callback
        self.hostname = hostname

    def on_close(self):
        self.connections.remove(self)

    def open(self):
        self.connections.add(self)

    def on_message(self, message):
        self.callback(message)
        # self.write_message(u"You said: " + message)
        pass

    @classmethod
    async def broadcast(cls, message):
        for connection in DeskSocketHandler.connections:
            connection.write_message(message)


def generate_dashboard(hostname, port):
    try:
        with open('frontend/app.js') as f:
            content = f.read()
            content = content.replace("<hostnamehere>", "ws://{}:{}/websocket".format(hostname, port))
            with open('frontend/application.js', 'w') as output:
                output.write(content)
    except IOError as e:
        return False


async def start_webserver(hostname, port, callback):
    generate_dashboard(hostname, port)
    static_handler = (r"/(.*)", StaticFileHandler, {"path": "frontend/", "default_filename": "index.html"})
    socket_handler = (r"/websocket", DeskSocketHandler, dict(callback=callback, hostname=hostname))

    app = Application(handlers=[socket_handler, static_handler])
    http_server = HTTPServer(app)
    http_server.listen(port)
