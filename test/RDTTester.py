import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from RDT import RDTSocket, SocketState


class TestRDT(unittest.TestCase):
    @staticmethod
    def new_socket(addr: tuple[str, int]) -> RDTSocket:
        socket = RDTSocket()
        socket.bind(addr)
        return socket

    def test_short_msg_transmit(self):
        thread_pool = ThreadPoolExecutor(max_workers=1)

        server_addr, client_addr = ('127.0.0.1', 8033), ('127.0.0.1', 8034)
        server_socket, client_socket = TestRDT.new_socket(server_addr), TestRDT.new_socket(client_addr)

        # run server
        future1 = thread_pool.submit(server_socket.accept)
        time.sleep(1)
        client_socket.connect(server_addr)
        accept_socket: RDTSocket = future1.result()

        # send 1
        for i in range(10):
            future2 = thread_pool.submit(accept_socket.recv)
            msg = f'Hello World{i}'
            t1 = time.time()
            client_socket.send(msg)
            server_rcv_data = future2.result()
            print(f'rcvd {server_rcv_data} within time:{time.time() - t1}')
            assert msg == server_rcv_data


        future3 = thread_pool.submit(client_socket.close)  # 远程先发close
        time.sleep(1)
        accept_socket.close()
        future3.result()
        assert accept_socket.get_state() == SocketState.CLOSED
        assert client_socket.get_state() == SocketState.CLOSED
        server_socket.close()
        thread_pool.shutdown()
        # print("any mem leak?")

    def test_demultiplex(self):
        thread_pool = ThreadPoolExecutor(max_workers=4)

        server_addr, client_addr,client2_addr = ('127.0.0.1', 8033), ('127.0.0.1', 8034), ('127.0.0.1', 8035)
        server_socket, client_socket,client_socket2 = TestRDT.new_socket(server_addr), TestRDT.new_socket(client_addr),TestRDT.new_socket(client2_addr)

        # run server
        future1 = thread_pool.submit(server_socket.accept)
        time.sleep(1)
        client_socket.connect(server_addr)
        accept_socket: RDTSocket = future1.result()

        future2 = thread_pool.submit(server_socket.accept)
        time.sleep(1)
        client_socket2.connect(server_addr)
        accept_socket2: RDTSocket = future2.result()


        # send 1

        client_accept1 = thread_pool.submit(accept_socket.recv)
        client_accept2 = thread_pool.submit(accept_socket2.recv)
        msg1 = f'Hello World {client_addr}'
        msg2 = f'Hello World {client2_addr}'
        args1 = (msg1,)
        args2 = (msg2,)
        thread_pool.submit(client_socket.send,*args1)
        thread_pool.submit(client_socket2.send,*args2)

        server_recv_from_client1 = client_accept1.result()
        server_recv_from_client2 = client_accept2.result()

        assert msg1 == server_recv_from_client1
        assert msg2 == server_recv_from_client2


        future3 = thread_pool.submit(client_socket.close)  # 远程先发close
        future4 = thread_pool.submit(client_socket2.close)
        time.sleep(1)
        accept_socket.close()
        accept_socket2.close()
        future3.result()
        future4.result()
        time.sleep(1)
        server_socket.close()
        thread_pool.shutdown()
        # print("any mem leak?")



if __name__ == "__main__":
    TestRDT().test_short_msg_transmit()