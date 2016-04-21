import socket
import sys
import threading
import time
from queue import Queue

from unicurses import *

import Message


def sock_recv_server(conn, killed, q):
    while not killed:
        try:
            # Receive bytes
            data = conn.recv(4096)
            if data:
                if data[:3] == b'\mq':
                    print("Connection closed by server. Exiting.")
                    global terminate
                    terminate = True
                elif data[:3] == b'\me':
                    msg = Message.Message(data, decrypt=True, key=PASSWORD)
                    try:
                        msg_text = msg.data.decode(encoding='utf-8')
                        msg_author = msg.author.decode(encoding='utf-8')
                        q.put(msg_author + ": " + msg_text)
                    except AttributeError:
                        reserve_print("Failed to parse an incoming message.")
                    except Exception as e:
                        reserve_print(e)
            else:
                continue
            time.sleep(0.2)
        except BlockingIOError as e:
            if e.errno == 11:
                pass
            if e.errno == 35:
                pass
            else:
                reserve_print("ERROR:", e)
                reserve_print(e)
                # break
    # came out of loop
    conn.close()


def ui_func(killed, print_queue, window):
    global COLS
    global LINES
    lines_list = []
    while not killed:
        d = print_queue.get()
        lines_list.append(d)

        window.clear()
        # redraw the last lines
        if len(lines_list) < LINES - 2:
            for i, line in enumerate(lines_list):
                window.addstr(LINES - 2 - len(lines_list) + i, 1, line)
        else:
            disp_lines = lines_list[3 - LINES:]
            for i, line in enumerate(disp_lines):
                window.addstr(LINES - 2 - len(disp_lines) + i, 1, line)
        window.refresh()


def load_config():
    with open("config", mode='r') as config_file:
        if config_file.readline().strip() == "[global]":
            port = int(config_file.readline().split("=")[1].strip())
            host = str(config_file.readline().split("=")[1].strip())
            return port, host


def reserve_print(*args):
    print(*args)
    global bottom_line
    sys.stdout.write('\n' + bottom_line)


def end_prog(status):
    echo()
    endwin()
    sys.exit(status)


def print_in_middle(win, starty, startx, width, string):
    if not win:
        win = stdscr
    y, x = getyx(win)
    if startx:
        x = startx
    if starty:
        y = starty
    if width == 0:
        width = 80
    length = len(string)
    temp = (width - length) / 2
    x = startx + int(temp)
    mvaddstr(y, x, string)


def get_param(prompt_string):
    stdscr.clear()
    field = newwin(7, 70, 4, 5)
    field.border(0)
    field.addstr(2, 3, prompt_string)
    field.refresh()
    echo()
    input = field.getstr(4, 8, 60)
    noecho()
    delwin(field)
    stdscr.refresh()
    return input


def popup_message(s, wait_button=False):
    stdscr.clear()
    field = newwin(5, 40, 8, 12)
    field.border(0)
    field.addstr(2, 3, s)
    field.refresh()
    if wait_button:
        field.getch()
    time.sleep(0.5)
    delwin(field)
    stdscr.clear()


stdscr = initscr()

# check for success
if stdscr == -1:
    print("ERROR: Failed to initialise UI. Ensure UniCurses is installed correctly and you are using a compatible terminal.")
    end_prog(1)

noecho()
global LINES
global COLS
LINES, COLS = getmaxyx(stdscr)

if not has_colors():
    endwin()
    print("Your terminal does not support color!")
    exit(1)

start_color()
init_pair(1, COLOR_WHITE, COLOR_BLUE)

port, host = load_config()

global terminate
terminate = False

global PASSWORD
PASSWORD = Message.hash_password('chiken')

global bottom_line
bottom_line = ''

border()
attron(COLOR_PAIR(1))
print_in_middle(stdscr, int(LINES / 2), 0, 0, "Welcome to Messenger. Press any key...")
attroff(COLOR_PAIR(1))
getch()

username = str(get_param("What's your name?"), encoding='utf-8')

popup_message("Hello, " + username + ".", wait_button=True)

#username = input("What's your name? " + Fore.BLUE)

# Open the socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Allow rebinding
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

try:
    sock.connect((host, port))
except ConnectionRefusedError:
    popup_message("Server refused connection. Check that server is running.", wait_button=True)
    end_prog(1)
except ConnectionError:
    popup_message("Server not found. Check server address.", wait_button=True)
    end_prog(1)
popup_message("Connecting to " + str(host) + " on port " + str(port) + "...")

# Wait for challenge from server and respond for authentication
challenge = sock.recv(32)
response = Message.enc_chal(challenge, PASSWORD)
sock.send(response)

# Disable blocking
sock.setblocking(True)

kill = False
sock_queue = Queue(0)
sock_recv_thread = threading.Thread(target=sock_recv_server, args=(sock, kill, sock_queue))
sock_recv_thread.setDaemon(True)
sock_recv_thread.start()

popup_message("Successfully connected to server.")

# Create the window for accepting input
input_window = newwin(1, COLS, LINES - 1, 0)
input_window.addstr(0, 0, "Type a message: ")
input_window.refresh()

# Create the window for displaying messages
msg_window = newwin(LINES - 1, COLS, 0, 0)
msg_window.addstr(0, (COLS // 2) - 10, "Messenger")
msg_window.refresh()

ui_thread = threading.Thread(target=ui_func, args=(kill, sock_queue, msg_window))
ui_thread.setDaemon(True)
ui_thread.start()

while True:
    # Main loop
    """
    if getch() == 27:  # Escape
        terminate = True
    """
    if terminate:
        end_prog(0)
    echo()

    input_window.clear()
    input_window.addstr(0, 0, "Type a message: ")
    input_window.refresh()

    msg = Message.Message(str(input_window.getstr(0, 17, COLS), encoding='utf-8'), author=username)
    noecho()

    input_window.clear()
    input_window.addstr(0, 0, "Type a message: ")
    input_window.refresh()

    msg.encrypt(PASSWORD)
    sock.send(msg.data)