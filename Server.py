import socket
import threading
import time
from queue import Queue
import queue

import Message


class SockSendThread(threading.Thread):
    def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs=None):
        super(SockSendThread, self).__init__(group=group, target=target, name=name)

        (self.conn, self.c) = args
        self.q = Queue()

    def run(self):
        while not self.c.quitf:
            try:
                message = self.q.get(block=False)
            except queue.Empty:
                time.sleep(0.1)
                continue
            try:
                #print("Sent data on socket: " + str(message))
                self.conn.send(message)
                self.q.task_done()
            except Exception as e:
                if '35' in str(e):
                    pass
                else:
                    print(e)
                    break
        # came out of loop
        self.conn.close()


def sock_recv_server(conn, c, recv_queue):
    conn.setblocking(True)
    while not c.quitf:
        try:
            # Receive bytes
            data = conn.recv(4096)
            if data:
                recv_queue.put(data)
                msg = Message.Message(data, decrypt=True, key=PASSWORD)
                msg_author = msg.author.decode(encoding='utf-8')
                msg_data = msg.data.decode(encoding='utf-8')
                try:
                    print("Data received on socket:", msg_author, msg_data)
                except Exception as e:
                    print(type(e))
                    print("you have the wrong password")
            else:
                continue
            time.sleep(0.1)
        except Exception as e:
            if e.errno == 11:
                pass
            if e.errno == 35:
                # BlockingIOError
                print(e)
                pass
            if e.errno == 54 or e.errno == 9:
                # Client has lost connection
                print("Client has disconnected.")
                break
            else:
                print("ERROR:", e)
                break
    # came out of loop
    conn.close()


def sock_loop(s, c):
    q = Queue()
    send_threads = []
    while not c.quitf:
        # check the Queue for data(s) to send
        while True:
            # keep looping until the queue is empty
            try:
                rcv_msg = q.get_nowait()
                for thread in send_threads:
                    thread.q.put(rcv_msg)
            except queue.Empty:
                # the queue has been emptied
                break

        # check the Carrier for data to send
        if c.send_str:
            for thread in send_threads:
                thread.q.put(c.send_str)
            c.send_str = None

        # obtain a new socket connection
        # wait to accept a connection - NON blocking call
        try:
            s.setblocking(False)
            conn, addr = s.accept()
            s.setblocking(True)
            if conn and addr:
                print(addr[0] + ':' + str(addr[1]) + " has connected.")
                print("Authenticating sock...")

                challenge = Message.random_chal()
                conn.send(challenge)
                print("Sent request...")
                while True:
                    try:
                        response = conn.recv(32)
                        if response:
                            break
                    except BlockingIOError:
                        time.sleep(0.1)
                if Message.enc_chal(challenge, PASSWORD) == response:
                    print("Client authenticated successfully.")

                    sock_recv_thread = threading.Thread(target=sock_recv_server, args=(conn, c, q))
                    sock_recv_thread.daemon = True
                    sock_recv_thread.start()

                    sock_send_thread = SockSendThread(args=(conn, c))
                    sock_send_thread.daemon = True
                    sock_send_thread.start()
                    send_threads.append(sock_send_thread)

                    conn.send(Message.Message('Welcome to the server.', author='Server').encrypt(PASSWORD))
                else:
                    # Client cannot authenticate. Disconnect it
                    print("Client has incorrect password. Disconnecting client...")
                    conn.send(b'\mq')
                    conn.close()
        except Exception as e:
            if e.errno == 11:
                # we don't got it yet
                time.sleep(0.1)
                pass
            if e.errno == 35:
                time.sleep(0.1)
                pass
            else:
                print("ERROR:", e)


class Carrier:
    def __init__(self):
        self.quitf = False
        self.send_str = None

    def send(self, ssr):
        self.send_str = ssr
        # block until watching function toggles back string to None
        while self.send_str:
            pass


def load_config():
    with open("config", mode='r') as config_file:
        if config_file.readline().strip() == "[global]":
            port = int(config_file.readline().split("=")[1].strip())
            host = str(config_file.readline().split("=")[1].strip())
            return port, host


HOST = ''
PORT = load_config()[0]

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind((HOST, PORT))
print("Socket bind complete")

# Allow rebinding
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

# Enable blocking
sock.setblocking(True)
sock.listen(10)
print("Socket now listening")

global PASSWORD
PASSWORD = Message.hash_password('chiken')

# Create the message queue
message_queue = Queue()

carr = Carrier()

# Start listening continuously
sock_thread = threading.Thread(target=sock_loop, args=(sock, carr))
sock_thread.daemon = True
sock_thread.start()

while True:
    time.sleep(2)
