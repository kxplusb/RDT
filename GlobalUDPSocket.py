import collections
import time
from enum import Enum

import select
from multiprocessing import Process, Queue, Lock
from queue import Empty
import pickle
import socket

from Header import RDTHeader
class LogMode(Enum):
    No = 1
    Long = 2
    Short = 3
    LatencyTest = 4
    BigFileCheck = 5


class Config:
    def __init__(self):
        self.log_mode: LogMode = LogMode.No#LogMode.Short  # LogMode.LatencyTest
        self.enable_proxy = False
        self.proxy_addr = None

        self.global_udp_time_out = 1  # recv timeout in 1s TODO need to set it?
        self.send_time_out = 1  # SYN,FIN传输5s后超时
        self.MSL = 3
        self.buf_size = 1024

        # if is -1, then inf retry
        self.SYN_Retry: int = -1
        self.SYN_ACK_Retry: int = -1
        self.FIN_Retry = -1
        self.FIN_Back_Retry = -1  # Fin ACK (passive close)


log_mode: LogMode = Config().log_mode


def packet_log(mode: LogMode, local_addr: (str, int), remote_addr: (str, int), packet: RDTHeader, send: bool,
               log_from: str = ""):
    if mode == LogMode.LatencyTest:
        print(
            f'{log_from} At time:{time.time() * 1000},At:{local_addr[1]} {"send to:" if send else "recv from:"}{remote_addr[1]}\t'
            f' with pkt(CASE,SYN,ACK,FIN,SEQ_Num,ACK_num,Payload):{(packet.test_case, packet.SYN, packet.ACK, packet.FIN, packet.SEQ_num, packet.ACK_num, packet.PAYLOAD)}\t')

    elif mode == LogMode.Short:
        timestamp_str = str(time.time())
        int_part = timestamp_str.split('.')[0][-4:]
        frac_part = timestamp_str.split('.')[1][:2]
        timestamp_str = int_part + "." + frac_part
        print(
            f'{log_from} At time:{timestamp_str},At:{local_addr[1]} {"send to:" if send else "recv from:"}{remote_addr[1]}\t'
            f' with pkt(CASE,SYN,ACK,FIN,SEQ_Num,ACK_num,Payload):{(packet.test_case, packet.SYN, packet.ACK, packet.FIN, packet.SEQ_num, packet.ACK_num, packet.PAYLOAD)}\t')

    elif mode == LogMode.BigFileCheck:
        timestamp_str = str(time.time())
        int_part = timestamp_str.split('.')[0][-4:]
        frac_part = timestamp_str.split('.')[1][:2]
        timestamp_str = int_part + "." + frac_part

        string = ""
        if packet.SYN == 1:
            string = f"SYN, seq:{packet.SEQ_num}, ack:{packet.ACK_num}, ack num:{packet.ACK_num}"
        elif packet.FIN == 1:
            string = f"FIN, seq:{packet.SEQ_num}, ack:{packet.ACK_num}, ack num:{packet.ACK_num}"
        elif packet.ACK == 1:
            string = f"ACK, num:{packet.ACK_num}"
        else:
            string = f"Data, seq:{packet.SEQ_num}"
        print(
            f'{log_from} Time:{timestamp_str},At:{local_addr[1]} {"send to:" if send else "recv from:"}{remote_addr[1]}\t' + string)




def receive_all_messages(sock, buffer_size):
    messages = collections.deque()

    while True:
        try:
            data, addr = sock.recvfrom(buffer_size)
            packet = RDTHeader().from_bytes(data)
            messages.append(packet)
        except BlockingIOError:
            break  # 没有数据时退出循环

    return messages


def start_udp_socket(listening_addr, real_remote, send_queue: Queue, recv_dict, lock):
    """
        需求：
        1. 创建socket，为接收注册事件
        2. 轮询如send_queue有数据则直接发送
        3. 轮询如果有数据到socket就recv接收
            -> 原子化（with lock）执行如下操作：
            1. 如果dict中有remote的地址，存入对应的queue
            2. 如果dict中没有remote的地址，存入("SYN",0)这个queue中，保证这个queue存在
        :param listening_addr:
        :param send_queue:
        :param recv_dict:
        :param lock:
        :return:
        """
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Bind the socket to the provided address
    sock.bind(listening_addr)
    # Set the socket to non-blocking
    sock.setblocking(False)

    try:
        cnt = 0
        while True:
            # print(f"cnt:{cnt}, {time.time()*1000},",end="")
            # Use select to wait for socket to be ready for I/O
            readable, writable, exceptional = select.select([sock], [sock], [sock], 0)

            # Handle incoming packets
            if sock in readable:
                # print(f"{time.time()*1000}do read,", end ="\n")
                # print(f"{time.time()}at {listening_addr}try recv data:{cnt}")
                m_queue = receive_all_messages(sock, 2980)
                packet = m_queue.pop()
                remote_addr = packet.src
                m_queue.append(packet)
                # Lock the recv_dict before updating
                # packet_log(log_mode, listening_addr, remote_addr, packet, send=False, log_from="///Before push In GlobalUDP: ")
                with lock:
                    if remote_addr not in recv_dict:
                        recv_dict[("SYN", 0)].put(m_queue)
                    else:
                        recv_dict[remote_addr].put(m_queue)

                packet_log(log_mode, listening_addr, remote_addr, packet, send=False, log_from="==In GlobalUDP: ")
                cnt+=1

            # Handle outgoing packets
            if sock in writable:
                try:
                    rcvbuf_size = sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
                    rwnd = int(rcvbuf_size / 256)
                    # Check if there is anything to send
                    next_packets: collections.deque = send_queue.get_nowait()
                    for next_packet in next_packets:
                        next_packet.RWND = rwnd
                        next_packet.compute_checksum()
                        serialized_packet = next_packet.to_bytes()

                        sock.sendto(serialized_packet, next_packet.tgt if real_remote is None else real_remote)

                        packet_log(log_mode, listening_addr, next_packet.tgt, next_packet, send=True,
                                   log_from="==In GlobalUDP: ")


                except Empty:
                    pass  # No packets to send

            # Handle exceptions
            if sock in exceptional:
                print("Socket exception.")
                break
            # cnt+=1
            # print()
    except Exception as e:
        print(f"Exception:{e}")
    finally:
        sock.close()
