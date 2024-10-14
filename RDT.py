import copy
import time
from collections import deque
from enum import Enum
from multiprocessing import Process, Manager, Lock, Queue
from queue import Empty

from GlobalUDPSocket import start_udp_socket, LogMode, Config, packet_log
from Header import RDTHeader, PacketType
from WindSizeAdapter import WindSizeAdapter
from utils.UInt32 import UInt32
from WindSizeAdapter import Event
class SocketState(Enum):
    CLOSED = 1
    SYN_SENT = 2
    Listen = 3
    SYN_RCVD = 4
    ESTABLISHED = 5
    CLOSE_WAIT = 6
    LAST_ACK = 7
    FIN_WAIT_1 = 8
    FIN_WAIT_2 = 9
    TIME_WAIT = 10
    SERVER_SOCKET = 11

class RDTBuffer():
    def __init__(self):
        self.__sending_buffer: deque[RDTHeader] = deque()
        self.__recving_buffer: deque[RDTHeader] = deque()

    def push_packet(self, paket: RDTHeader, size: int) -> bool:
        """
        把paket放入deque，如果放入的deque的大小大于size,则返回true，表示要发送
        :param paket:
        :return:
        """
        self.__sending_buffer.append(paket)
        return len(self.__sending_buffer) >= size

    def pop_sending_buffer(self) -> deque[RDTHeader]:
        buf = self.__sending_buffer
        self.__sending_buffer = deque()
        return buf

    def is_recving_buffer_empty(self)->bool:
        return len(self.__recving_buffer)==0

    def get_packet(self)->RDTHeader:
        return self.__recving_buffer.pop()

    def set_recving_buffer(self, new:deque[RDTHeader]):
        assert self.is_recving_buffer_empty()
        self.__recving_buffer = new



class RDTSocket():
    # WARNING！这个类不是线程安全的！同时调用bind和accept会出现出乎意料的结果
    def __init__(self) -> None:
        self.config: Config = Config()
        self.udp_process: Process = None
        self.manager: Manager = None
        self.send_queue: Queue = None
        self.recv_dict: dict[(str, int), Queue[deque[RDTHeader]]] = None
        self.dict_read_lock: Lock = None
        self.seq_num: UInt32 = UInt32(0)
        self.local_addr: (str, int) = None
        self.remote_addr: (str, int) = None
        self.proxy_server_addr: (str, int) = None
        self.is_server: bool = False
        self.state = SocketState.CLOSED
        self.prev_ack: UInt32 = None
        self.is_child: bool = False
        self.__close_wait = 1
        self.RDT_buffer: RDTBuffer = RDTBuffer()

    def __set_ack(self, cnt: UInt32):
        self.prev_ack = cnt

    def __add_seq(self, cnt: int):
        self.seq_num += cnt

    def __get_from_queue_with_timeout(self, timeout) -> (RDTHeader, bool):
        if self.RDT_buffer.is_recving_buffer_empty():
            self.RDT_buffer.set_recving_buffer(self.recv_dict[self.remote_addr].get(timeout=timeout))
        pkt: RDTHeader = self.RDT_buffer.get_packet()

        packet_log(self.config.log_mode, self.local_addr, self.remote_addr, pkt, send=False)
        return pkt, pkt.packet_verify()

    def __get_from_queue(self) -> (RDTHeader, bool):
        if self.RDT_buffer.is_recving_buffer_empty():
            self.RDT_buffer.set_recving_buffer(self.recv_dict[self.remote_addr].get())

        pkt: RDTHeader = self.RDT_buffer.get_packet()

        packet_log(self.config.log_mode, self.local_addr, self.remote_addr, pkt, send=False)

        return pkt, pkt.packet_verify()

    def __try_get_from_queue(self) -> (RDTHeader, bool):
        if self.RDT_buffer.is_recving_buffer_empty():
            self.RDT_buffer.set_recving_buffer(self.recv_dict[self.remote_addr].get(block=False))

        pkt: RDTHeader = self.RDT_buffer.get_packet()
        return pkt, pkt.packet_verify()

    def __send_to_queue(self, pkt: RDTHeader, size=1):
        pkt = copy.copy(pkt)
        assert self.remote_addr is not None
        pkt.set_src_dest(self.local_addr, self.remote_addr)
        pkt.compute_checksum()

        packet_log(self.config.log_mode, self.local_addr, self.remote_addr, pkt, send=True)
        if self.RDT_buffer.push_packet(pkt, size):
            self.send_queue.put(self.RDT_buffer.pop_sending_buffer())

            if self.config.log_mode == LogMode.Short:
                print("Pushing buffer Occurs")
    def __force_send_to_queue(self, pkt: RDTHeader, size=1):
        assert self.remote_addr is not None
        pkt.set_src_dest(self.local_addr, self.remote_addr)
        pkt.compute_checksum()

        packet_log(self.config.log_mode, self.local_addr, self.remote_addr, pkt, send=True)
        self.RDT_buffer.push_packet(pkt, size)
        self.send_queue.put(self.RDT_buffer.pop_sending_buffer())

        if self.config.log_mode == LogMode.Short:
            print("Pushing buffer Occurs")



    def __add_remote_to_queue(self, remote_addr: (str, int)):
        self.recv_dict[remote_addr] = self.manager.Queue()

    def bind(self, address: (str, int)):  # type: ignore
        """
        When trying to establish a connection. The socket must be bound to an address 
        and listening for connections. address is the address bound to the socket on 
        the other end of the connection.

     
        
        params: 
            address:    Target IP address and its port
        """
        self.local_addr = address
        self.manager = Manager()
        self.send_queue = self.manager.Queue()
        self.recv_dict = self.manager.dict()
        self.dict_read_lock = Lock()
        self.udp_process = Process(target=start_udp_socket, args=(
            self.local_addr, self.proxy_server_addr,
            self.send_queue, self.recv_dict, self.dict_read_lock))
        self.__add_remote_to_queue(("SYN", 0))
        self.udp_process.start()

    def __child_socket_bind(self, local, manager, send_queue, recv_dict, lock, udp_process):
        self.local_addr = local
        self.manager = manager
        self.send_queue = send_queue
        self.recv_dict = recv_dict
        self.dict_read_lock = lock
        self.udp_process = udp_process
        self.is_child = True

    def accept(self):  # type: ignore
        """
        When using this SOCKET to create an RDT SERVER, it should accept the connection
        from a CLIENT. After that, an RDT connection should be established.
        Please note that this function needs to support multithreading and be able to 
        establish multiple socket connections. Messages from different sockets should 
        be isolated from each other, requiring you to multiplex the data received at 
        the underlying UDP.

        This function should be blocking. 

        """
        self.is_server = True
        self.remote_addr = ("SYN", 0)
        accept_socket = RDTSocket()
        accept_socket.__set_state(SocketState.Listen)
        accept_socket.__child_socket_bind(self.local_addr, self.manager, self.send_queue, self.recv_dict,
                                          self.dict_read_lock,
                                          self.udp_process)

        # 收到SYN
        pkt, valid = self.__get_from_queue()
        remote_seq = UInt32(pkt.SEQ_num)
        assert pkt.SYN == 1 and valid
        self.__set_state(SocketState.SYN_RCVD)
        accept_socket.remote_addr = pkt.src
        self.__add_remote_to_queue(pkt.src)
        # 返回SYN ACK
        resp = PacketType.get_SYN(self.seq_num)
        PacketType.add_ACK(resp, remote_seq, 20)
        accept_socket.__send_to_queue(resp)

        # 收到ACK
        pkt, valid = accept_socket.__get_from_queue()
        remote_ack = UInt32(pkt.ACK_num)
        assert remote_ack == self.seq_num and valid
        accept_socket.__set_ack(remote_ack)
        accept_socket.__add_seq(1)
        accept_socket.__set_state(SocketState.ESTABLISHED)
        return accept_socket

    def connect(self, address: (str, int)):  # type: ignore
        """
        When using this SOCKET to create an RDT client, it should send the connection
        request to target SERVER. After that, an RDT connection should be established.

        params:
            address:    Target IP address and its port
        """
        # TODO 最简单版本
        self.remote_addr = address
        self.__add_remote_to_queue(address)

        # 发SYN
        self.__set_state(SocketState.SYN_SENT)
        self.__send_to_queue(PacketType.get_SYN(self.seq_num))

        # 收SYN ACK
        pkt, valid = self.__get_from_queue()
        ack_num = UInt32(pkt.SEQ_num)
        assert pkt.ACK == 1 and pkt.SYN == 1 and valid
        self.__set_ack(ack_num)
        self.__add_seq(1)
        # 回ACK
        self.__set_state(SocketState.ESTABLISHED)
        self.__send_to_queue(PacketType.get_ACK(self.seq_num, ack_num, 20))

    def __is_state(self, state: SocketState):
        return self.state == state

    def __set_state(self, state: SocketState):
        if self.config.log_mode == LogMode.Short:
            print(f'{(self.local_addr, self.remote_addr)}:{self.state}->{state}')
        self.state = state

    def send(self, data=None, tcpheader: RDTHeader = None, test=0):
        """
        RDT can use this function to send specified data to a target that has already
        established a reliable connection. Please note that the corresponding CHECKSUM
        for the specified data should be calculated before computation. Additionally,
        this function should implement flow control during the sending phase. Moreover,
        when the data to be sent is too large, this function should be able to divide
        the data into multiple chunks and send them to the destination in a pipelined
        manner.

        params:
            data:       The data that will be sent.
            tcpheader:  Message header.Include SYN, ACK, FIN, CHECKSUM, etc. Use this
                        attribute when needed.
            test_case:  Indicate the test case will be used in this experiment
        """
        # TODO Assigned to ZC
        # print("sending data to")
        # print(f"At send{self.seq_num}")
        whole_pkt = RDTHeader(test_case=test) if tcpheader is None else tcpheader
        dataLen = 256
        origin_timeout = 1
        data_list = [''] + [data[i: i + dataLen] for i in range(0, len(data), dataLen)] + ['']
        data_ack = [0 for _ in range(len(data_list))]
        data_send = [0 for _ in range(len(data_list))]
        data_time = [0 for _ in range(len(data_list))]
        pointer = 1
        #windowSize = len(data_list) + 5
        WindAdapter = WindSizeAdapter(500, 700)
        if(len(data_list)>500):
            WindAdapter.enter_aggressive()
        windowSize = 8 if test < 12 else WindAdapter.wind_size(Event.timeout, 0)
        cycle = 0
        cnt = 0
        while True:
            for i in range(pointer, pointer + windowSize):
                # print((time.time()*1000)%100000)
                if i < len(data_list) and data_ack[i] == 0:
                    whole_pkt.PAYLOAD = data_list[i]
                    whole_pkt.PACKET_SIZE = len(data_list[i])
                    whole_pkt.SEQ_num = int(self.seq_num + i)
                    if i == pointer + windowSize-1 or i == len(data_list)-1:
                        self.__send_to_queue(whole_pkt, 1)
                    else:
                        self.__send_to_queue(whole_pkt, windowSize+1)
                    data_time[i] = time.time()
                    data_send[i] += 1
            # print("first point at sending data to")
            while True:  # 这里的条件还要考量一下
                timeout = 3
                timeoutNum = pointer
                # print("window size: " + str(windowSize))
                for i in range(pointer, pointer + windowSize):
                    if i < len(data_list) and data_time[i] == 0:
                        cnt = cnt + 1
                        if cnt == windowSize:
                            cnt = 0
                            cycle = cycle + 1
                        whole_pkt.PAYLOAD = data_list[i]
                        whole_pkt.PACKET_SIZE = len(data_list[i])
                        whole_pkt.SEQ_num = int(self.seq_num + i)
                        if i == pointer + windowSize - 1 or i == len(data_list) - 1:
                            self.__send_to_queue(whole_pkt, 1)
                        else:
                            self.__send_to_queue(whole_pkt, windowSize+1)
                        data_time[i] = time.time()
                        data_send[i] += 1
                        continue
                    if (i < len(data_list)
                        and origin_timeout - time.time() + data_time[i] < timeout) \
                            and data_ack[i] == 0:
                        timeout = origin_timeout - time.time() + data_time[i]
                        timeoutNum = i
                try:
                    pkt, valid = self.__get_from_queue_with_timeout(timeout=max(timeout, 0.01))
                except Empty:
                    windowSize = 8 if test < 12 else WindAdapter.wind_size(Event.timeout, cycle)
                    if timeout == 3:
                        print("all packets in the window timeout.")
                        break
                    print("packet: " + str(timeoutNum) + " timeout: " + str(timeout))
                    # print("data_ack: " + str(data_ack))
                    whole_pkt.PAYLOAD = data_list[timeoutNum]
                    whole_pkt.PACKET_SIZE = len(data_list[timeoutNum])
                    whole_pkt.SEQ_num = int(self.seq_num + timeoutNum)
                    self.__send_to_queue(whole_pkt)
                    data_time[timeoutNum] = time.time()
                    data_send[timeoutNum] += 1
                    continue
                if not valid:
                    print("checksum is not valid")
                    continue
                if pkt.FIN != 0:
                    self.seq_num += len(data)
                    return
                if pkt.ACK == 1 and pkt.ACK_num == 0:
                    WindAdapter.rwnd = pkt.RWND
                    windowSize = 8 if test < 12 else WindAdapter.wind_size(Event.dup_ack, cycle)
                    print("all packets in the window need to be resend due to the file damage.")
                    break
                if pkt.ACK == 1 and self.seq_num < pkt.ACK_num < self.seq_num + len(data_list):
                    if pkt.SEQ_num != 0:
                        # todo: 特殊处理
                        pass
                    WindAdapter.rwnd = pkt.RWND
                    windowSize = 8 if test < 12 else WindAdapter.wind_size(Event.ack, cycle)
                    data_ack[pkt.ACK_num - int(self.seq_num)] += 1
                    if pkt.ACK_num == self.seq_num + pointer:
                        pointer += 1
                        if pointer == len(data_list):
                            break
                        while data_ack[pointer] > 0:
                            pointer += 1
                            if pointer == len(data_list):
                                break
                if pointer == len(data_list):
                    break
            if pointer == len(data_list):
                break

        for i in range(1, len(data_list)):
            if data_send[i] != data_ack[i]:
                print("data not same: " + str(i))
        self.seq_num += len(data)
        print("exit sending data to")
        # print("end sending data to")
        # whole_pkt = RDTHeader(test_case=test_case) if tcpheader is None else tcpheader
        # whole_pkt.PAYLOAD = data
        # self.__send_to_queue(whole_pkt)

    def recv(self):
        """
        You should implement the basic logic for receiving data in this function, and
        verify the data. When corrupted or missing data packets are detected, a request
        for retransmission should be sent to the other party.

        This function should be bolcking.
        """
        # TODO Assigned to ZC
        # print("Receiving data...")
        self.prev_ack += 1
        # first = True
        # print(f"At rcvd{self.prev_ack}")
        data_list = ['']
        data_buffer: dict[int, RDTHeader] = dict()
        while True:
            # print(f"recv time1: {(time.time()*1000)%100000}")
            pkt, valid = self.__get_from_queue()
            # print(f"recv time2: {(time.time()*1000)%100000}")
            # print("hereeeeeeeeeeeeeeeeeeeeeeeeeeeeee0000000000000")
            if not valid:
                self.__send_to_queue(PacketType.get_ACK(UInt32(0), UInt32(0), pkt.test_case))
                continue
            # if first:
            #     first = False
            #     print("first" + str((time.time() * 1000) % 100000))
            self.__send_to_queue(PacketType.get_ACK(UInt32(0), pkt.SEQ_num, pkt.test_case))
            # print("hereeeeeeeeeeeeeeeeeeeeeeeeeeeeee")
            num = pkt.SEQ_num - int(self.prev_ack)
            # print(num)
            # print("Received data: " + str(pkt.PAYLOAD) + num)
            if num == len(data_list):
                data_list.append(pkt.PAYLOAD)
                while len(data_list) in data_buffer:
                    data_list.append(data_buffer[len(data_list)])
                if data_list[len(data_list) - 1] == '':
                    break
            else:
                data_buffer[num] = pkt.PAYLOAD
        print("exit Receiving data...")
        data = ''.join(data_list)
        self.__set_ack(self.prev_ack + UInt32(len(data)) - 1)
        # print("==================")
        # print((time.time()*1000)%100000)
        return data

    def close(self):
        """
        Close current RDT connection.
        You should follow the 4-way-handshake, and then the RDT connection will be terminated.
        """
        if self.is_server:
            return
        first_fin: RDTHeader = None
        while first_fin is None:
            try:
                pkt, verify = self.__try_get_from_queue()
                if pkt.FIN != 1:
                    return
                    # print(f"How can that be? pkt:{pkt}")
                    # continue
                first_fin = pkt
            except Empty:
                # first FIN
                break
        if first_fin is None:
            self.__set_state(SocketState.FIN_WAIT_1)
            self.__send_to_queue(PacketType.get_FIN(self.seq_num))  # 发FIN

            cnt = 0
            recv_FIN = False
            while cnt < self.__close_wait:
                cnt += 1
                try:
                    pkt, valid = self.__get_from_queue_with_timeout(timeout=5)  # 收ACK
                except Exception as e:
                    self.__send_to_queue(PacketType.get_FIN(self.seq_num))
                    continue
                remote_ack = UInt32(pkt.ACK_num)
                # if valid and pkt.ACK == 1 and remote_ack == self.seq_num:
                if pkt.FIN == 1:
                    remote_seq = UInt32(pkt.SEQ_num)
                    recv_FIN = True
                elif valid and pkt.ACK == 1:
                    break
                else:
                    self.__send_to_queue(PacketType.get_FIN(self.seq_num))
                    print(f"At A, How can packet in this manner?:{pkt}")

            self.__set_state(SocketState.FIN_WAIT_2)

            while not recv_FIN:
                try:
                    pkt, valid = self.__get_from_queue_with_timeout(timeout=10)  # 收FIN
                except:
                    return
                remote_seq = UInt32(pkt.SEQ_num)
                if valid and pkt.FIN == 1:
                    break
                elif pkt.ACK == 1 and valid:
                    continue
                else:
                    self.__send_to_queue(PacketType.get_FIN(self.seq_num))
                    print(f"At C, How can packet in this manner?:{pkt}")
            self.__set_state(SocketState.TIME_WAIT)

            time.sleep(1)
            self.__send_to_queue(PacketType.get_ACK(self.seq_num, remote_seq, test_case=20))  # 回ACK
            self.__set_state(SocketState.CLOSED)
        else:
            remote_seq = UInt32(first_fin.SEQ_num)  # 收到FIN,发ACK
            self.__send_to_queue(PacketType.get_ACK(self.seq_num, remote_seq, test_case=20))
            self.__set_state(SocketState.CLOSE_WAIT)
            time.sleep(0.5)
            self.__set_state(SocketState.LAST_ACK)  # 发FIN
            self.__send_to_queue(PacketType.get_FIN(self.seq_num))

            cnt = 0
            while cnt < self.__close_wait:
                cnt += 1
                try:
                    pkt, valid = self.__get_from_queue_with_timeout(timeout=5)  # 收到ACK
                except Exception as e:
                    self.__send_to_queue(PacketType.get_ACK(self.seq_num, remote_seq, test_case=20))
                    self.__send_to_queue(PacketType.get_FIN(self.seq_num))
                    continue
                ack_num = UInt32(pkt.ACK_num)
                # if ack_num == self.seq_num and valid:
                if valid:
                    break
                else:
                    self.__send_to_queue(PacketType.get_ACK(self.seq_num, remote_seq, test_case=20))
                    self.__send_to_queue(PacketType.get_FIN(self.seq_num))
                    print(f"At B, How can packet in this manner?:{pkt}")
            self.__add_seq(1)
            self.__set_ack(ack_num)
            self.__set_state(SocketState.CLOSED)

        # 简单地资源清理,不考虑有的没的 TODO 得确定没有人在用才能close，很糟
        if not self.is_child:
            self.udp_process.terminate()
            self.manager.shutdown()

    def get_state(self) -> SocketState:
        '''
        For testing use
        :return:
        '''
        return self.state

