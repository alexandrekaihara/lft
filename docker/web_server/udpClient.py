import socket
from time import sleep

msgFromClient       = "Hello UDP Server"
bytesToSend         = str.encode(msgFromClient)
serverAddressPort   = ("127.0.0.1", 1234)
bufferSize          = 1472

UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
while True:
    UDPClientSocket.sendto(bytesToSend, serverAddressPort)
    sleep(2)
    print("Sending new message to " + serverAddressPort[0] + " port " + str(serverAddressPort[1]))

