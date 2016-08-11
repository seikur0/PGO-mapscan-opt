from __future__ import print_function

import json
import numbers
import os

import re
from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
from twisted.python import log

ignore_file = "res/.uploader.ignore"

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
    if not isinstance(seconds, numbers.Number):
        log.err(seconds)
        seconds = 1
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
    pattern = re.compile("spawns[0-9]*\..+_.+(\.json|\.txt)")
    ignored = []
    if os.path.isfile(ignore_file):
        with open(ignore_file) as f:
            for line in f:
                ignored.append(line.strip().replace("res/", ''))

    for file in os.listdir("res"):
        if pattern.match(file) is not None and file not in ignored:
            fileout = "res/" + file
            yield fileout


def file_len(fname):
    i, l = 0, 0
    with open(fname) as f:
        for i, l in enumerate(f):
            pass
    s = i + 1 - 1
    if s < 1:
        s = 1
    return s


def complete_file(file):
    with open(ignore_file, 'a') as f:
        f.write(file.replace("res/", '') + "\n")


@inlineCallbacks
def gotProtocol(p):
    for file in find_files():
        if os.path.isfile(file):
            linenum = file_len(file)
            current = 0
            with open(file) as f:
                print("found file {} with {} pokemon".format(file.replace("res/", ''), linenum))
                for line in f:
                    if line.startswith("Name"):
                        continue
                    current += 1
                    p.sendMessage(line)
                    # Give control back to the reactor to actually send the data
                    update_tick(linenum=linenum, current=current)
                    yield wait(0.1)
            complete_file(file)

    if update_tick.counter == 0:
        print('')
        print("You seem to have no uploadable files.")
        print("Wait a bit for the map to accumulate more pokemon.")

    print('')
    p.transport.loseConnection()
    print("Transfered {} pokemon sightings!".format(update_tick.counter))
    print("Transfer done, waiting for data to be send by the os!")
    yield shutdown(1 + (update_tick.counter / 100))
    print("Thanks for helping out!")


def update_tick(dot='#', linenum=None, current=None):
    update_tick.counter += 1
    print(dot, end='', flush=True)
    if update_tick.counter % 100 == 0:
        print('')
        if linenum and current:
            perc = int((float(current) / float(linenum) * 10000) / 100)
            print("You have send {}/{} from this file ({}%)!".format(current, linenum, perc))
        print('Already send {} pokemon this session!'.format(update_tick.counter))


update_tick.counter = 0

if __name__ == '__main__':
    point = TCP4ClientEndpoint(reactor, url, port)
    d = point.connect(GreeterFactory())
    d.addCallback(gotProtocol)

    d.addErrback(shutdown)
    reactor.run()
