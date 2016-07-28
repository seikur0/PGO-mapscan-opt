import os
from socket import socket

url = 'h2569107.stratoserver.net'
port = 8007

def main():
    counter = 0
    fp = 'res/upload{}.log'.format

    sock = socket()
    sock.connect((url, port))
    print("check file {} exists {}".format(fp(counter),os.path.isfile(fp(counter))))
    while os.path.isfile(fp(counter)):
        with open(fp(counter)) as f:
            for line in f:
                print("sending line {}".format(line))
                sock.sendall(line+"\n")
        os.remove(fp(counter))
        counter += 1

    sock.close()
if __name__ == '__main__':
    main()