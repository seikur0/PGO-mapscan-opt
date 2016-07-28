import os
from socket import socket

url = 'h2569107.stratoserver.net'
port = 8007

def main():
    counter = 0
    fp = 'res/upload{}.log'.format

    sock = socket()
    sock.connect((url, port))
    while os.path.isfile(fp(counter)):
        with open(fp(counter)) as f:
            for line in f:
                sock.sendall(line)
        counter += 1

if __name__ == '__main__':
    main()