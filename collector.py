import json
import os

import re
from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver

ignore_file = "/res/.uploader.ignore"

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

    def sendPokemonLine(self, line):
        spl = line.split("\t")
        obj = {
            "pokemon_id": spl[1],
            "last_modified_timestamp_ms": int(float(spl[5])),
            "spawnpoint_id": spl[2],
            "longitude": spl[4],
            "latitude": spl[3],
            "encounter_id": spl[7],
            "time_till_hidden_ms": int(float(spl[6]))
        }

        msg = json.dumps(obj)
        self.sendLine(msg.encode('UTF-8'))

    def sendMessage(self, msg=''):
        if self.clientInstance is not None:
            self.sendPokemonLine(msg)
        else:
            self.messageQueue.append(msg)

    def connectionMade(self):
        print("Connected to server, start sending!")
        self.clientReady()

    def clientReady(self):
        self.clientInstance = "Ready"
        for msg in self.messageQueue:
            self.sendMessage(msg)


class GreeterFactory(Factory):
    def buildProtocol(self, addr):
        return Greeter()


def stop_reaktor(_):
    reactor.stop()


def shutdown(seconds, result=None):
    d = Deferred()
    d.addCallback(stop_reaktor)
    reactor.callLater(seconds, d.callback, result)
    return d


def wait(seconds, result=None):
    """Returns a deferred that will be fired later"""
    d = Deferred()
    reactor.callLater(seconds, d.callback, result)
    return d


def find_files():
    pattern = re.compile("spawns[0-9]*\..+_.+\.json")
    ignored = []
    if os.path.isfile(ignore_file):
        with open(ignore_file) as f:
            ignored = f.readlines()
    print(ignored)
    for file in os.listdir("res"):
        if pattern.match(file) is not None and file not in ignored:
            yield "res/"+file


def complete_file(file):
    with open(ignore_file, 'a') as f:
        f.write(file + "\n")


@inlineCallbacks
def gotProtocol(p):
    for file in find_files():
        if os.path.isfile(file):
            with open(file) as f:
                for line in f:
                    if line.startswith("Name"):
                        continue
                    p.sendMessage(line)
                    # Give control back to the reactor to actually send the data
                    update_tick()
                    yield wait(0.1)
            complete_file(file)

    print('')
    p.transport.loseConnection()
    print("Transfered {} pokemon sightings!".format(update_tick.counter))
    print("Transfer done, waiting for data to be send by the os!")
    yield shutdown(10)
    print("Thanks for helping out!")


def update_tick(dot='#'):
    update_tick.counter += 1
    print(dot, end='', flush=True)
    if update_tick.counter % 100 == 0:
        print('')
        print('Already send {} pokemon this session!'.format(update_tick.counter))


update_tick.counter = 0

if __name__ == '__main__':
    point = TCP4ClientEndpoint(reactor, url, port)
    d = point.connect(GreeterFactory())
    d.addCallback(gotProtocol)
    from twisted.python import log

    d.addErrback(log.err)
    reactor.run()
