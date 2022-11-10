    import socket
    import sys
    from time import sleep

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = ('localhost', 2000)
    sock.connect(server_address)
    message = 'This is the message.  It will be repeated.'

    try:
        while True:
            print ("Sending message to ", server_address[0])
            sock.sendall(message)
            amount_received = 0
            amount_expected = len(message)
            sleep(2)
    finally:
        print >>sys.stderr, 'closing socket'
        sock.close()
            