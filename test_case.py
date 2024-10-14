import socket
import time
from RDT import RDTSocket
from multiprocessing import Process
import signal

# connect proxy server 
import sys

proxy_server_address = ('10.16.52.172', 12234)   # ProxyServerAddress
fromSenderAddr = ('10.16.52.172', 12345)         # FromSender
toReceiverAddr = ('10.16.52.172', 12346)         # ToSender
fromReceiverAddr = ('10.16.52.172', 12347)       # FromReceiver
toSenderAddr = ('10.16.52.172', 12348)           # ToReceiver

resultAddr = ('10.16.52.172', 12230)

#TODO change the adress to your address
sender_address = ("10.32.70.94", 12344)         # Your sender address
receiver_address = ("10.32.70.94", 12349)       # Your receiver address

# sender_address = ("10.26.48.10", 12344)         # Your sender address
# receiver_address = ("10.26.48.10", 12349)       # Your receiver address

# sender_address = ("10.27.96.162", 12344)         # Your sender address
# receiver_address = ("10.27.96.162", 12349)       # Your receiver addres


# connect locally server

# proxy_server_address = ('127.0.0.1', 12234)
# fromSenderAddr = ('127.0.0.1', 12345)
# toReceiverAddr = ('127.0.0.1', 12346)
# fromReceiverAddr = ('127.0.0.1', 12347)
# toSenderAddr = ('127.0.0.1', 12348)
#
# sender_address = ("127.0.0.1", 12244)
# receiver_address = ("127.0.0.1", 12249)
# resultAddr = ("127.0.0.1", 12230)
num_test_case = 16


class TimeoutException(Exception):
    pass


def handler(signum, frame):
    raise TimeoutException


# signal.signal(signal.SIGALRM, handler)

def test_case():
    sender_sock = None
    reciever_sock = None

    # TODO: You could change the range of this loop to test specific case(s) in local test.

    for i in range(11, 16):
        if sender_sock:
            del sender_sock
        if reciever_sock:
            del reciever_sock
        sender_sock = RDTSocket()  # You can change the initialize RDTSocket()
        reciever_sock = RDTSocket()  # You can change the initialize RDTSocket()
        print(f"Start test case : {i}")

        try:
            result = RDT_start_test(sender_sock, reciever_sock, sender_address, receiver_address, i)
        except Exception as e:
            print(e)
        finally:
            print("Final handle")
            client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_sock.connect(resultAddr)

            client_sock.sendall(f"{sender_address}-{receiver_address}:{i}".encode())

            response = client_sock.recv(1024)

            client_sock.close()

            print(f"proxy result for test case {i} {response.decode()}")

            if response.decode() == 'True' and result:
                print(f"test case {i} pass")
            else:
                print(f"test case {i} fail")

            #############################################################################
            # TODO you should close your socket, and release the resource, this code just a
            # demo. you should make some changes based on your code implementation or you can 
            # close them in the other places.
            #############################################################################
            time.sleep(1)

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(f"{sender_address}-{receiver_address}".encode(), proxy_server_address)

            time.sleep(2)


def RDT_start_test(sender_sock, reciever_sock, sender_address, receiver_address, test_case):
    sender = Process(target=RDT_send, args=(sender_sock, sender_address, receiver_address, test_case))
    receiver = Process(target=RDT_receive, args=(reciever_sock, receiver_address, test_case))

    receiver.start()
    time.sleep(1)
    sender.start()

    # if test_case < 5:
    #     signal.alarm(20)
    # else:
    #     signal.alarm(120)

    sender.join()
    receiver.join()
    time.sleep(1)

    # signal.alarm(0)

    if test_case < 5:
        return True
    else:
        # TODO you may need to change the path, if you want.
        return test_file_integrity('original.txt', 'transmit.txt')


def RDT_send(sender_sock: RDTSocket, source_address, target_address, test_case):
    """
        You should refer to your own implementation to implement this code. the sender should specify the Source_address, Target_address, and test_case in the Header of all packets sent by the receiver.
        params: 
            target_address:    Target IP address and its port
            source_address:    Source IP address and its port
            test_case:         The rank of test case
    """
    data_blocks = []
    file_path = 'original.txt'  # You can modify the path of file. Howerver, if you change this file, you need to modify the input for function test_file_integrity()

    sock = sender_sock
    sock.proxy_server_addr = fromSenderAddr

    sock.bind(source_address)
    sock.connect(target_address)
    time.sleep(1)
    if test_case >= 5:
        with open(file_path, "r") as file:
            data = str(file.readlines()[0])
        sock.send(data=data, test=test_case)

    else:
        data = "Short Message test"
        sock.send(data=data, test=test_case)

    time.sleep(3)
    sock.close()  # TODO I close at here
    print("sender finished")


def RDT_receive(reciever_sock: RDTSocket, source_address, test_case):
    """
        You should refer to your own implementation to implement this code. the receiver should specify the Source_address, Target_address, and test_case in the Header of all packets sent by the receiver.
        params: 
            source_address:    Source IP address and its port
            test_case:         The rank of test case
    """
    sock = reciever_sock
    sock.proxy_server_addr = fromReceiverAddr
    sock.bind(source_address)
    server_sock = sock.accept()

    if test_case >= 5:
        data = server_sock.recv()
        with open("transmit.txt", "w") as file:
            file.write(data)

    else:
        data = server_sock.recv()

    server_sock.close()
    time.sleep(1)
    sock.close()
    print(f"rcv finished with data:{data}")


def test_file_integrity(original_path, transmit_path):
    with open(original_path, 'rb') as file1, open(transmit_path, 'rb') as file2:
        while True:
            block1 = file1.read(4096)
            block2 = file2.read(4096)

            if block1 != block2:
                return False

            if not block1:
                break

    return True


if __name__ == '__main__':
    print('Hello, World!')
    print('This is a test.')
    t = time.time()
    test_case()
    print(f"running {time.time() - t} s")