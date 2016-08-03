from twisted.web.server import Site
from twisted.web.static import File
from twisted.internet import reactor
import sys

resource = None
factory = None

def server_start(port):
    resource = File("")
    factory = Site(resource)
    sys.stdout.write('[+] Webserver started, listening on port {}.\n'.format(port))
    reactor.listenTCP(port, factory)
    reactor.addSystemEventTrigger('before', 'shutdown', server_end)
    reactor.run(installSignalHandlers=False)



def server_end():
    reactor.close()

if __name__ == '__main__':
    server_start(8000)