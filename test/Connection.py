import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import contextmanager
from queue import Queue

from RDT import SocketState
from Header import RDTHeader
from RDT import RDTSocket
from utils.StoppableThread import StoppableThread

sender_proxy = ('127.0.0.1', 12345)
recver_addr = ('127.0.0.1', 12346)
recver_proxy = ('127.0.0.1', 12347)
sender_addr = ('127.0.0.1', 12348)


class UDPSocket:
    def __init__(self, local: (str, int), remote: (str, int), timeout=None):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(timeout)
        self.socket.bind(local)
        self.remote = remote

    def send(self, pkt: RDTHeader):
        self.socket.sendto(pkt.to_bytes(), self.remote)

    def recv_pkt(self) -> RDTHeader:
        data, addr = self.socket.recvfrom(296)
        pkt = RDTHeader()
        pkt.from_bytes(data)
        # print(f"rcvd!:{pkt}")
        return pkt

    def close(self):
        self.socket.close()


def single_bind(server_sock: RDTSocket, server_addr: (str, int),
                recv_sock: RDTSocket, recv_addr: (str, int)) \
        -> (UDPSocket, UDPSocket):
    """
    Binding sockets
    :return: (proxy_sender_recv, proxy_recver_recv)
    """
    # server
    server_sock.proxy_server_addr = sender_proxy
    server_sock.bind(server_addr)
    # recver
    recv_sock.proxy_server_addr = recver_proxy
    recv_sock.bind(recv_addr)

    # udp channel
    proxy_sender = UDPSocket(local=sender_proxy, remote=server_addr, timeout=3)
    proxy_recver = UDPSocket(local=recver_proxy, remote=recv_addr, timeout=3)
    return proxy_sender, proxy_recver


@contextmanager
def send_by_server(data: str):
    try:
        tester = Test(data)
        tester.send_by_server()
        yield tester.get_proxy_sock()
    finally:
        tester.close()


@contextmanager
def send_by_client(data: str):
    try:
        tester = Test(data)
        tester.send_by_client()
        yield tester.get_proxy_sock()
    finally:
        tester.close()


@contextmanager
def handshake(data: str):
    try:
        tester = Test(data)
        tester.handshake()
        yield (tester.get_proxy_sock(), tester.check_connection_established)
    finally:
        tester.close()


@contextmanager
def farewell(data: str):
    try:
        tester = Test(data)
        funcs = tester.finish_data_transmit()
        yield (tester.get_proxy_sock(), funcs, tester.check_connection_closed)
    finally:
        tester.close()


@contextmanager
def farewell_raw(data: str):
    try:
        tester = Test(data)
        funcs = tester.finish_data_transmit()
        sender, recver = tester.get_sender_recver_sock()
        accept = tester.get_accept_sock()
        yield (tester.get_proxy_sock(), funcs, tester.check_connection_closed, (sender, recver, accept))
    finally:
        tester.close()


class UDPSocketWrapper:
    def __init__(self, sock: UDPSocket, queue: Queue):
        self.__sock = sock
        self.__queue = queue
        self.__end = False

    def send(self, data: RDTHeader):
        self.__sock.send(data)

    def recv_pkt(self) -> RDTHeader:
        if self.__end:
            return None
        while self.__queue.empty():
            if self.__end:
                return None
            pass
        return self.__queue.get()

    def set_end(self):
        self.__end = True


class Test:
    def __init__(self, data: str):
        self.__server_sock: RDTSocket = RDTSocket()
        self.__recver_sock: RDTSocket = RDTSocket()
        self.__accept_sock: RDTSocket = None
        self.__proxy_send: UDPSocket = None
        self.__proxy_recv: UDPSocket = None
        self.__thread_pool = ThreadPoolExecutor(max_workers=20)
        self.__data_len = 256
        self.__data_send: str = data
        self.__result_future: Future = None
        self.__proxy_sender_queue: Queue[RDTHeader] = Queue()
        self.__proxy_recver_queue: Queue[RDTHeader] = Queue()
        self.__proxy_sender_thread: StoppableThread = None
        self.__proxy_recver_thread: StoppableThread = None

        self.__send_future: Future = None
        self.__recv_future: Future = None

    def check_connection_established(self):
        self.__accept_sock = self.__send_future.result()
        return (self.__accept_sock.get_state() == SocketState.ESTABLISHED
                and self.__recver_sock.get_state() == SocketState.ESTABLISHED)

    def check_connection_closed(self):
        return (self.__accept_sock.get_state() == SocketState.CLOSED
                and self.__recver_sock.get_state() == SocketState.CLOSED)

    def get_sender_recver_sock(self) -> (RDTSocket, RDTSocket):
        return self.__server_sock, self.__recver_sock

    def get_accept_sock(self) -> RDTSocket:
        assert self.__accept_sock is not None  # 必须调用established Connection后才能get它
        return self.__accept_sock

    def get_proxy_sock(self) -> (UDPSocketWrapper, UDPSocketWrapper):
        send_wrapper = UDPSocketWrapper(self.__proxy_send, self.__proxy_sender_queue)
        recv_wrapper = UDPSocketWrapper(self.__proxy_recv, self.__proxy_recver_queue)
        return send_wrapper, recv_wrapper

    def __start_proxy(self):
        assert self.__proxy_sender_thread is None or not self.__proxy_sender_thread.is_alive()
        assert self.__proxy_recver_thread is None or not self.__proxy_recver_thread.is_alive()
        assert self.__proxy_send is not None
        assert self.__proxy_recv is not None

        def inf_recv(proxy: UDPSocket, queue: Queue):
            while True:
                try:
                    queue.put(proxy.recv_pkt())
                except socket.timeout as _:
                    continue
                except Exception as e:
                    print("!")
                    raise e
                # TODO 远程主机强迫关闭了一个现有的连接。remote为127.0.0.1 12348

        self.__proxy_sender_thread = StoppableThread(target=inf_recv,
                                                     args=(self.__proxy_send, self.__proxy_sender_queue))
        self.__proxy_recver_thread = StoppableThread(target=inf_recv,
                                                     args=(self.__proxy_recv, self.__proxy_recver_queue))
        self.__proxy_sender_thread.start()
        self.__proxy_recver_thread.start()

    def close_proxy(self):
        if self.__proxy_sender_thread is not None:
            self.__proxy_sender_thread.stop()
        if self.__proxy_recver_thread is not None:
            self.__proxy_recver_thread.stop()

        while self.__proxy_recver_thread.is_alive():
            pass
        while self.__proxy_sender_thread.is_alive():
            pass
        self.__proxy_send.close()
        self.__proxy_recv.close()

    def normal_transmit(self, future1, future2):
        """
        normal transmit until two future is done
        :param future1:
        :param future2:
        :return:
        """
        while not (future1.done() and future2.done()):
            if not self.__proxy_sender_queue.empty():
                pkt = self.__proxy_sender_queue.get()
                self.__proxy_recv.send(pkt)
            if not self.__proxy_recver_queue.empty():
                pkt = self.__proxy_recver_queue.get()
                self.__proxy_send.send(pkt)

    def init_proxy(self):
        self.__proxy_send, self.__proxy_recv = single_bind(self.__server_sock, sender_addr, self.__recver_sock,
                                                           recver_addr)
        self.__start_proxy()

    def handshake(self) -> (Future, Future):
        self.init_proxy()
        self.__send_future = self.__thread_pool.submit(self.__server_sock.accept)
        self.__recv_future = self.__thread_pool.submit(self.__recver_sock.connect, sender_addr)
        return self.__send_future, self.__recv_future

    def establish_connection(self):
        send_future, recv_future = self.handshake()
        self.normal_transmit(send_future, recv_future)
        self.__accept_sock = send_future.result()

    def send_by_server(self) -> (Future, Future):
        """
        Initialize a scenario for single file transmit, operating upd sock and operate to simulate congestion
        :return: (proxy_sender_recv, proxy_recver_recv)
        """
        self.establish_connection()
        args = (self.__data_send, None, 2)
        send_future = self.__thread_pool.submit(self.__accept_sock.send, *args)
        self.__result_future = self.__thread_pool.submit(self.__recver_sock.recv)
        return send_future, self.__result_future

    def send_by_client(self) -> (Future, Future):
        self.establish_connection()
        args = (self.__data_send, None, 2)
        recver_future = self.__thread_pool.submit(self.__recver_sock.send, *args)
        self.__result_future = self.__thread_pool.submit(self.__accept_sock.recv)
        return recver_future, self.__result_future

    def finish_data_transmit(self):
        """

        :return: 关闭accept_sock和recv_sock的函数
        """
        accept_future, recver_future = self.send_by_server()
        self.normal_transmit(accept_future, recver_future)
        return self.close_accept, self.close_recver

    def close_accept(self):
        return self.close_sock(self.__accept_sock)

    def close_recver(self):
        self.close_sock(self.__recver_sock)

    def close_sock(self, sock: RDTSocket) -> Future:
        return self.__thread_pool.submit(sock.close)

    def normal_close(self):
        recv_future = self.__thread_pool.submit(self.__recver_sock.close)
        accept_future = self.__thread_pool.submit(self.__accept_sock.close)
        self.normal_transmit(accept_future, recv_future)

    def close(self):
        if self.__result_future is not None:
            res = self.__result_future.result()
            assert self.__data_send == res
        if ((self.__accept_sock is not None and self.__accept_sock.get_state() != SocketState.CLOSED)
                or self.__recver_sock.get_state() != SocketState.CLOSED):
            self.normal_close()
        time.sleep(2)
        self.__server_sock.close()
        self.close_proxy()
        self.__thread_pool.shutdown()
        print("All closed")
