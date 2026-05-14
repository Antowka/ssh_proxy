#!/usr/bin/env python3

import paramiko
import socket
import select
import threading
import time
import logging
import sys

HOST = "example.com"
PORT = 22
USER = "root"
PASSWORD = "Passw0rd"
PROXY_PORT = 8787
RECONNECT_DELAY = 5

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/opt/ssh_proxy/ssh-proxy.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SSHProxy:
    def __init__(self):
        self.client = None
        self.transport = None
        self.running = False

    def connect(self):
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                HOST,
                port=PORT,
                username=USER,
                password=PASSWORD,
                banner_timeout=30,
                auth_timeout=30
            )
            self.transport = self.client.get_transport()
            self.transport.set_keepalive(30)
            logger.info(f"Connected to {HOST}")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self):
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
        self.client = None
        self.transport = None

    def handle_socks_client(self, client_sock):
        logger.debug("New SOCKS client connection")
        try:
            client_sock.settimeout(10)
            data = client_sock.recv(2)
            if not data or data[0] != 5:
                client_sock.close()
                return

            num_methods = data[1]
            methods = client_sock.recv(num_methods)
            logger.debug(f"SOCKS5 methods: {methods.hex()}")

            client_sock.send(b'\x05\x00')

            data = client_sock.recv(4)
            if not data or data[0] != 5 or data[2] != 0:
                client_sock.close()
                return

            addr_type = data[1]
            if addr_type == 1:
                dst_addr = socket.inet_ntoa(client_sock.recv(4))
            elif addr_type == 3:
                addr_len = ord(client_sock.recv(1))
                dst_addr = client_sock.recv(addr_len).decode()
            else:
                client_sock.close()
                return

            dst_port = int.from_bytes(client_sock.recv(2), 'big')
            logger.info(f"SOCKS request: {dst_addr}:{dst_port}")

            if not self.transport or not self.transport.is_active():
                logger.warning("SSH transport not active")
                client_sock.close()
                return

            try:
                channel = self.transport.open_channel(
                    'direct-tcpip',
                    (dst_addr, dst_port),
                    ('127.0.0.1', 0)
                )

                reply = b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00'
                client_sock.send(reply)

                self.forward_data(client_sock, channel)
                channel.close()
            except Exception as e:
                logger.error(f"Channel error: {e}")

        except Exception as e:
            logger.error(f"SOCKS error: {e}")
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def forward_data(self, client_sock, channel):
        try:
            while self.running and channel.active:
                r, w, e = select.select([client_sock, channel], [], [], 1)
                if client_sock in r:
                    data = client_sock.recv(4096)
                    if not data:
                        break
                    channel.send(data)
                if channel in r:
                    data = channel.recv(4096)
                    if not data:
                        break
                    client_sock.send(data)
        except Exception as e:
            logger.debug(f"Forward error: {e}")

    def run(self):
        self.running = True
        while self.running:
            if not self.connect():
                logger.info(f"Reconnecting in {RECONNECT_DELAY}s...")
                time.sleep(RECONNECT_DELAY)
                continue

            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(('0.0.0.0', PROXY_PORT))
            server.listen(50)
            logger.info(f"SOCKS proxy listening on 0.0.0.0:{PROXY_PORT}")

            while self.running:
                try:
                    server.settimeout(1.0)
                    client, addr = server.accept()
                    logger.info(f"Connection from {addr}")
                    thread = threading.Thread(target=self.handle_socks_client, args=(client,))
                    thread.daemon = True
                    thread.start()
                except socket.timeout:
                    if self.transport and not self.transport.is_active():
                        logger.warning("SSH tunnel lost")
                        break
                except Exception as e:
                    if self.running:
                        logger.error(f"Server error: {e}")
            server.close()

            if self.running:
                self.disconnect()
                logger.info(f"Reconnecting in {RECONNECT_DELAY}s...")
                time.sleep(RECONNECT_DELAY)


if __name__ == "__main__":
    proxy = SSHProxy()
    try:
        proxy.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        proxy.running = False
        proxy.disconnect()
        sys.exit(0)
