import time
import unittest
from Connection import send_by_client, send_by_server, UDPSocketWrapper

single_word_data = "1234567890"
multiple_word_data = "a" * 256 + "b" * 256 + "c" * 256


# TODO 需要测试的可能：
# 1. 丢包
# 2. 乱序抵达
class TestFileDrop(unittest.TestCase):
    def test_no_drop_in_order1(self):
        with send_by_server(data=single_word_data) as socks:
            server_proxy: UDPSocketWrapper = socks[0]
            client_proxy: UDPSocketWrapper = socks[1]

            pkt = server_proxy.recv_pkt()
            assert pkt.PAYLOAD == single_word_data
            client_proxy.send(pkt)

            pkt = server_proxy.recv_pkt()
            assert pkt.PAYLOAD == ''
            client_proxy.send(pkt)

            pkt = client_proxy.recv_pkt()
            assert pkt.ACK == 1
            server_proxy.send(pkt)

            pkt = client_proxy.recv_pkt()
            assert pkt.ACK == 1
            server_proxy.send(pkt)

    def test_no_drop_in_order2(self):
        with send_by_client(data=single_word_data) as socks:
            server_proxy: UDPSocketWrapper = socks[0]
            client_proxy: UDPSocketWrapper = socks[1]

            pkt = client_proxy.recv_pkt()
            assert pkt.PAYLOAD == single_word_data
            server_proxy.send(pkt)

            pkt = server_proxy.recv_pkt()
            assert pkt.ACK == 1
            client_proxy.send(pkt)

            pkt = client_proxy.recv_pkt()
            assert pkt.PAYLOAD == ''
            server_proxy.send(pkt)

            pkt = server_proxy.recv_pkt()
            assert pkt.ACK == 1
            client_proxy.send(pkt)

    def test_drop_in_order1(self):
        with send_by_server(data=single_word_data) as socks:
            server_proxy: UDPSocketWrapper = socks[0]
            client_proxy: UDPSocketWrapper = socks[1]

            pkt = server_proxy.recv_pkt()
            assert pkt.PAYLOAD == single_word_data
            # client_proxy.send(pkt)

            pkt = server_proxy.recv_pkt()
            assert pkt.PAYLOAD == ''
            client_proxy.send(pkt)

            pkt = client_proxy.recv_pkt()
            assert pkt.ACK == 1
            server_proxy.send(pkt)

            pkt = server_proxy.recv_pkt()
            assert pkt.PAYLOAD == single_word_data
            client_proxy.send(pkt)

            pkt = client_proxy.recv_pkt()
            assert pkt.ACK == 1
            server_proxy.send(pkt)

            print("test_drop_in_order1 done")

    def test_no_drop_not_in_order1(self):
        with send_by_server(data=single_word_data) as socks:
            server_proxy: UDPSocketWrapper = socks[0]
            client_proxy: UDPSocketWrapper = socks[1]

            pkt1 = server_proxy.recv_pkt()
            assert pkt1.PAYLOAD == single_word_data

            pkt = server_proxy.recv_pkt()
            assert pkt.PAYLOAD == ''
            client_proxy.send(pkt)

            pkt = client_proxy.recv_pkt()
            assert pkt.ACK == 1
            server_proxy.send(pkt)
            client_proxy.send(pkt1)

            pkt = client_proxy.recv_pkt()
            assert pkt.ACK == 1
            server_proxy.send(pkt)

    def test_corrupt_checksum(self):
        with send_by_server(data=single_word_data) as socks:
            server_proxy: UDPSocketWrapper = socks[0]
            client_proxy: UDPSocketWrapper = socks[1]

            pkt = server_proxy.recv_pkt()
            assert pkt.PAYLOAD == single_word_data
            pkt.PAYLOAD = "AAAAA"  # corrupt
            client_proxy.send(pkt)

            pkt = server_proxy.recv_pkt()
            seq_end_num = pkt.SEQ_num
            assert pkt.PAYLOAD == ''
            client_proxy.send(pkt)

            pkt = client_proxy.recv_pkt()
            assert pkt.ACK == 1 and pkt.ACK_num == 0  # retransmission occurs
            server_proxy.send(pkt)

            pkt = client_proxy.recv_pkt()
            assert pkt.ACK == 1 and pkt.ACK_num == seq_end_num
            server_proxy.send(pkt)

            pkt = server_proxy.recv_pkt()
            assert pkt.PAYLOAD == single_word_data
            client_proxy.send(pkt)

            pkt = client_proxy.recv_pkt()
            assert pkt.ACK == 1
            server_proxy.send(pkt)


if __name__ == "__main__":
    TestFileDrop().test_corrupt_checksum()
