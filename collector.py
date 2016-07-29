import os

from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.protocol import Factory, Protocol
from twisted.protocols.basic import LineReceiver

url = 'h2569107.stratoserver.net'
port = 8007


class Greeter(LineReceiver):
    def __init__(self):
        self.clientInstance = None
        self.messageQueue = []

    def rawDataReceived(self, data):
        pass

    def lineReceived(self, line):
        pass

    def sendMessage(self, msg=''):
        if self.clientInstance is not None:
            self.sendLine(msg.encode('UTF-8'))
        else:
            self.messageQueue.append(msg)

    def connectionMade(self):
        print("Connected!")
        self.clientReady()


    def clientReady(self):
        self.clientInstance = "Ready"
        for msg in self.messageQueue:
            self.sendMessage(msg)


class GreeterFactory(Factory):
    def buildProtocol(self, addr):
        return Greeter()


def gotProtocol(p):
    counter = 0
    fp = 'res/upload{}.log'.format

    print("check file {} exists {}".format(fp(counter),os.path.isfile(fp(counter))))
    while os.path.isfile(fp(counter)):
        with open(fp(counter)) as f:
            for line in f:
                print("sending line {}".format(line))
                p.sendMessage(line)
        os.remove(fp(counter))
        counter += 1
    p.transport.loseConnection()
    print("Transfer done, you can now shutdown this script!")

if __name__ == '__main__':
    point = TCP4ClientEndpoint(reactor, url, port)
    d = point.connect(GreeterFactory())
    d.addCallback(gotProtocol)
    from twisted.python import log
    d.addErrback(log.err)
    reactor.run()



