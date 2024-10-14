import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import random
from Connection import farewell, farewell_raw, sender_addr, recver_addr, UDPSocketWrapper
from GlobalUDPSocket import Config, SocketState
from Header import RDTHeader
from RDT import RDTSocket

data = "123"
MSL = Config().MSL
time_out = Config().send_time_out

"""
346是recver, 348是sender
"""


# TODO 同时需要测试包抵达超过2MSL的情况，这种情况需要处理操作系统内部的RST错误
class FarewellTest(unittest.TestCase):

    def test_no_drop(self):
        with farewell(data=data) as ((udp_send, udp_recv), (accept_close, recver_close), check_all_closed):
            """
            Four way farewell
            """
            accept_close()
            pkt: RDTHeader = udp_send.recv_pkt()
            assert pkt.FIN == 1
            udp_recv.send(pkt)

            pkt = udp_recv.recv_pkt()
            assert pkt.ACK == 1
            udp_send.send(pkt)

            recver_close()
            pkt = udp_recv.recv_pkt()
            assert pkt.FIN == 1
            udp_send.send(pkt)

            pkt = udp_send.recv_pkt()
            assert pkt.ACK == 1
            udp_recv.send(pkt)

            time.sleep(3 * MSL)
            assert check_all_closed()

    def test_drop_fin1(self):
        with farewell(data=data) as ((udp_send, udp_recv), (accept_close, recver_close), check_all_closed):
            """
            Four way farewell
            """
            accept_close()
            pkt: RDTHeader = udp_send.recv_pkt()
            assert pkt.FIN == 1
            # just drop fin from sender

            pkt: RDTHeader = udp_send.recv_pkt()
            assert pkt.FIN == 1
            udp_recv.send(pkt)

            pkt = udp_recv.recv_pkt()
            assert pkt.ACK == 1
            udp_send.send(pkt)

            recver_close()
            pkt = udp_recv.recv_pkt()
            assert pkt.FIN == 1
            udp_send.send(pkt)

            pkt = udp_send.recv_pkt()
            assert pkt.ACK == 1
            udp_recv.send(pkt)

            time.sleep(3 * MSL)
            assert check_all_closed()

    def test_drop_ack1(self):
        with farewell(data=data) as ((udp_send, udp_recv), (accept_close, recver_close), check_all_closed):
            """
            Four way farewell
            """
            accept_close()
            pkt: RDTHeader = udp_send.recv_pkt()
            assert pkt.FIN == 1
            udp_recv.send(pkt)

            pkt = udp_recv.recv_pkt()
            assert pkt.ACK == 1
            # just drop it

            pkt: RDTHeader = udp_send.recv_pkt()
            assert pkt.FIN == 1
            udp_recv.send(pkt)

            pkt = udp_recv.recv_pkt()
            assert pkt.ACK == 1
            udp_send.send(pkt)

            recver_close()
            pkt = udp_recv.recv_pkt()
            assert pkt.FIN == 1
            udp_send.send(pkt)

            pkt = udp_send.recv_pkt()
            assert pkt.ACK == 1
            udp_recv.send(pkt)

            time.sleep(3 * MSL)
            assert check_all_closed()

    def test_drop_fin2(self):
        with farewell(data=data) as ((udp_send, udp_recv), (accept_close, recver_close), check_all_closed):
            """
            Four way farewell
            """
            accept_close()
            pkt: RDTHeader = udp_send.recv_pkt()
            assert pkt.FIN == 1
            udp_recv.send(pkt)

            pkt = udp_recv.recv_pkt()
            assert pkt.ACK == 1
            udp_send.send(pkt)

            recver_close()
            pkt = udp_recv.recv_pkt()
            assert pkt.FIN == 1
            # just drop it
            pkt = udp_recv.recv_pkt()
            assert pkt.FIN == 1
            udp_send.send(pkt)

            pkt = udp_send.recv_pkt()
            assert pkt.ACK == 1
            udp_recv.send(pkt)

            time.sleep(3 * MSL)
            assert check_all_closed()

    def test_drop_ack2(self):
        with farewell(data=data) as ((udp_send, udp_recv), (accept_close, recver_close), check_all_closed):
            """
            Four way farewell
            """
            accept_close()
            pkt: RDTHeader = udp_send.recv_pkt()
            assert pkt.FIN == 1
            udp_recv.send(pkt)

            pkt = udp_recv.recv_pkt()
            assert pkt.ACK == 1
            udp_send.send(pkt)

            recver_close()
            pkt = udp_recv.recv_pkt()
            assert pkt.FIN == 1
            udp_send.send(pkt)

            pkt = udp_send.recv_pkt()
            assert pkt.ACK == 1
            # just drop it

            pkt = udp_recv.recv_pkt()
            assert pkt.FIN == 1
            udp_send.send(pkt)

            pkt = udp_send.recv_pkt()
            assert pkt.ACK == 1
            udp_recv.send(pkt)

            time.sleep(3 * MSL)
            assert check_all_closed()

    def test_ack_delay(self):
        """
        FIN delay, ACK delay都会有这种情况，见草稿图1
        :return:
        """
        with farewell(data=data) as ((udp_send, udp_recv), (accept_close, recver_close), check_all_closed):
            accept_close()
            pkt: RDTHeader = udp_send.recv_pkt()
            assert pkt.FIN == 1
            udp_recv.send(pkt)

            pkt = udp_recv.recv_pkt()
            assert pkt.ACK == 1
            delay = pkt  # 放到delay池子里

            pkt: RDTHeader = udp_send.recv_pkt()
            assert pkt.FIN == 1
            udp_recv.send(pkt)

            pkt = udp_recv.recv_pkt()
            assert pkt.ACK == 1
            delay2 = pkt

            udp_send.send(delay)
            udp_send.send(delay2)

            recver_close()
            pkt = udp_recv.recv_pkt()
            assert pkt.FIN == 1
            udp_send.send(pkt)

            pkt = udp_send.recv_pkt()
            assert pkt.ACK == 1
            udp_recv.send(pkt)

            time.sleep(3 * MSL)
            assert check_all_closed()

    def test_ack2_delay(self):
        with farewell(data=data) as ((udp_send, udp_recv), (accept_close, recver_close), check_all_closed):
            """
            Four way farewell
            """
            accept_close()
            pkt: RDTHeader = udp_send.recv_pkt()
            assert pkt.FIN == 1
            udp_recv.send(pkt)

            pkt = udp_recv.recv_pkt()
            assert pkt.ACK == 1
            udp_send.send(pkt)

            recver_close()
            pkt = udp_recv.recv_pkt()
            assert pkt.FIN == 1
            udp_send.send(pkt)

            pkt = udp_send.recv_pkt()
            assert pkt.ACK == 1
            delay = pkt

            pkt = udp_recv.recv_pkt()
            assert pkt.FIN == 1
            udp_send.send(pkt)

            pkt = udp_send.recv_pkt()
            assert pkt.ACK == 1
            delay2 = pkt

            udp_recv.send(delay)
            udp_recv.send(delay2)

            time.sleep(3 * MSL)
            assert check_all_closed()

    def rounding(self, cnt:int, policy):
        for i in range(cnt):
            with farewell_raw(data=data) as (
                    (udp_send, udp_recv), (accept_close, recver_close), check_all_closed,
                    (rdt_sender, rdt_recver, rdt_accept)):
                """
                Four way farewell
                """
                udp_send: UDPSocketWrapper
                udp_recv: UDPSocketWrapper
                rdt_sender: RDTSocket
                rdt_recver: RDTSocket
                rdt_accept: RDTSocket

                accept_close()
                rcver_closed = False
                queue = []
                sender_future, recver_future = None, None
                thread_pool = ThreadPoolExecutor(max_workers=2)
                while not check_all_closed():
                    if not rcver_closed and rdt_recver.get_state() == SocketState.CLOSE_WAIT:
                        recver_close()

                    if sender_future is None:
                        sender_future = thread_pool.submit(udp_send.recv_pkt)
                    if recver_future is None:
                        recver_future = thread_pool.submit(udp_recv.recv_pkt)

                    while not (sender_future.done() or recver_future.done()):
                        if check_all_closed():
                            break
                        pass
                    if sender_future.done():
                        pkt = sender_future.result()
                        queue.append(pkt)
                        sender_future = None

                    if recver_future.done():
                        pkt = recver_future.result()
                        queue.append(pkt)
                        recver_future = None

                    # 这里就是对接收包的处理策略
                    policy(queue=queue,udp_send=udp_send,udp_recv=udp_recv)

                udp_send.set_end()
                udp_recv.set_end()
                thread_pool.shutdown()
            print(f"round:{i} finished")

    def test_normal(self):
        def policy(queue:list[RDTHeader],udp_send:UDPSocketWrapper,udp_recv:UDPSocketWrapper):
            while len(queue) != 0:
                pkt: RDTHeader = queue.pop()
                if pkt.tgt == sender_addr:
                    udp_send.send(pkt)
                elif pkt.tgt == recver_addr:
                    udp_recv.send(pkt)
                else:
                    raise 'ERR'

        self.rounding(5,policy)

    def test_random_drop(self):
        def policy(queue: list[RDTHeader], udp_send: UDPSocketWrapper, udp_recv: UDPSocketWrapper):
            while len(queue) != 0:
                pkt: RDTHeader = queue.pop()
                rnd = random.random()
                if rnd < 0.25:  # 25%丢包概率
                    print(
                        f"========DROPPING PKT(CASE,SYN,ACK,FIN,SEQ_Num,ACK_num):{(pkt.test_case, pkt.SYN, pkt.ACK, pkt.FIN, pkt.SEQ_num, pkt.ACK_num)}")
                    continue
                if pkt.tgt == sender_addr:
                    udp_send.send(pkt)
                elif pkt.tgt == recver_addr:
                    udp_recv.send(pkt)
                else:
                    raise 'ERR'

        self.rounding(5, policy)

    def test_congestion(self):
        def policy(queue: list[RDTHeader], udp_send: UDPSocketWrapper, udp_recv: UDPSocketWrapper):
            while len(queue) != 0:
                pkt: RDTHeader = queue.pop()
                rnd = random.random()
                if rnd<0.5:#0.25不发
                    print(f"========Congesting PKT(CASE,SYN,ACK,FIN,SEQ_Num,ACK_num,src,dest):"
                          f"{(pkt.test_case, pkt.SYN, pkt.ACK, pkt.FIN, pkt.SEQ_num, pkt.ACK_num, pkt.src, pkt.tgt)}")
                    time.sleep(time_out)
                    return
                if pkt.tgt == sender_addr:
                    udp_send.send(pkt)
                elif pkt.tgt == recver_addr:
                    udp_recv.send(pkt)
                else:
                    raise 'ERR'

        self.rounding(5, policy)

    # print(f"========Shuffle, Sending PKT(CASE,SYN,ACK,FIN,SEQ_Num,ACK_num,src,dest):"
    #       f"{(pkt.test_case, pkt.SYN, pkt.ACK, pkt.FIN, pkt.SEQ_num, pkt.ACK_num, pkt.src, pkt.tgt)}")