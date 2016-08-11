from twisted.internet import reactor
from twisted.web.static import File
from twisted.web.resource import Resource, EncodingResourceWrapper
from twisted.web.server import Site, GzipEncoderFactory

import sys
import os

root = None
factory = None

class WFile(File):
    def getChild(self, path, request):
        child = File.getChild(self, path, request)
        return EncodingResourceWrapper(child, [GzipEncoderFactory()])

def server_start(port, workdir):
    mywebsite = WFile(workdir + '/webres')
    root = EncodingResourceWrapper(mywebsite, [GzipEncoderFactory()])
    factory = Site(root)
    sys.stdout.write('[+] Webserver started, listening on port {}.\n'.format(port))
    reactor.listenTCP(port, factory)
    reactor.addSystemEventTrigger('before', 'shutdown', server_end)
    reactor.run(installSignalHandlers=False)

def server_end():
    reactor.close()

if __name__ == '__main__':
    workdir = os.path.dirname(os.path.realpath(__file__))
    server_start(8000, workdir)