#!/usr/bin/env python3

import subprocess
import time
import signal
import os
import sys
import socket
import select
import threading

HOST = "example.com"
PORT = 22
USER = "root"
PASSWORD = "PaSsW0rd"

PROXY_PORT = 8787
HTTP_PROXY_PORT = 7878
SOCKS_PROXY_HOST = "127.0.0.1"
SOCKS_PROXY_PORT = 8787
RECONNECT_DELAY = 5

LOG_FILE = "/opt/ssh_proxy/ssh-proxy.log"


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} - {msg}\n"
    with open(LOG_FILE, "a") as f:
        f.write(line)
    print(line.strip())


class HTTPProxy:
    def __init__(self):
        self.process = None
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()
        log(
            f"HTTP proxy starting on 0.0.0.0:{HTTP_PROXY_PORT} -> socks5://{SOCKS_PROXY_HOST}:{SOCKS_PROXY_PORT}"
        )
        return True

    def _run_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", HTTP_PROXY_PORT))
        server.listen(100)
        log(f"HTTP proxy server listening on 0.0.0.0:{HTTP_PROXY_PORT}")

        while self.running:
            try:
                server.settimeout(1.0)
                try:
                    client_socket, addr = server.accept()
                except socket.timeout:
                    continue

                thread = threading.Thread(
                    target=self._handle_client, args=(client_socket,)
                )
                thread.daemon = True
                thread.start()
            except Exception as e:
                if self.running:
                    log(f"HTTP proxy server error: {e}")

        server.close()

    def _handle_client(self, client_socket):
        try:
            data = client_socket.recv(4096)
            if not data:
                client_socket.close()
                return

            lines = data.decode("utf-8", errors="ignore").split("\r\n")
            if not lines:
                client_socket.close()
                return

            first_line = lines[0]
            method = first_line.split(" ")[0] if first_line else ""

            host_port = None
            for line in lines[1:]:
                if line.lower().startswith("host:"):
                    host_port = line.split(":", 1)[1].strip()
                    break

            if not host_port:
                client_socket.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                client_socket.close()
                return

            if method == "CONNECT":
                self._handle_connect(client_socket, host_port)
                return

            if ":" in host_port:
                host, port = host_port.split(":")
                port = int(port)
            else:
                host = host_port
                port = 80

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((SOCKS_PROXY_HOST, SOCKS_PROXY_PORT))

            sock.sendall(b"\x05\x01\x00")
            resp = sock.recv(2)
            if len(resp) < 2 or resp[0] != 5 or resp[1] != 0:
                sock.close()
                client_socket.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                client_socket.close()
                return

            addr_type = 3
            addr_bytes = bytes([len(host)]) + host.encode()
            port_bytes = bytes([port >> 8, port & 0xFF])
            connect_cmd = b"\x05\x01\x00" + bytes([addr_type]) + addr_bytes + port_bytes
            sock.sendall(connect_cmd)
            resp = sock.recv(10)
            if len(resp) < 10 or resp[1] != 0:
                sock.close()
                client_socket.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                client_socket.close()
                return

            sock.sendall(data)
            self._tunnel(client_socket, sock)
        except Exception as e:
            pass
        finally:
            try:
                client_socket.close()
            except:
                pass
            try:
                sock.close()
            except:
                pass

    def _handle_connect(self, client_socket, host_port):
        try:
            if ":" in host_port:
                host, port = host_port.split(":")
                port = int(port)
            else:
                host = host_port
                port = 443

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((SOCKS_PROXY_HOST, SOCKS_PROXY_PORT))

            sock.sendall(b"\x05\x01\x00")
            resp = sock.recv(2)
            if len(resp) < 2 or resp[0] != 5 or resp[1] != 0:
                sock.close()
                client_socket.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                client_socket.close()
                return

            addr_type = 3
            addr_bytes = bytes([len(host)]) + host.encode()
            port_bytes = bytes([port >> 8, port & 0xFF])
            connect_cmd = b"\x05\x01\x00" + bytes([addr_type]) + addr_bytes + port_bytes
            sock.sendall(connect_cmd)
            resp = sock.recv(10)
            if len(resp) < 10 or resp[1] != 0:
                sock.close()
                client_socket.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                client_socket.close()
                return

            client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self._tunnel(client_socket, sock)
        except Exception as e:
            try:
                client_socket.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            except:
                pass
        finally:
            try:
                client_socket.close()
            except:
                pass
            try:
                sock.close()
            except:
                pass

    def _tunnel(self, client, server):
        try:
            while True:
                r, _, _ = select.select([client, server], [], [], 60)
                if not r:
                    break
                for s in r:
                    data = s.recv(4096)
                    if not data:
                        return
                    other = server if s is client else client
                    other.sendall(data)
        except:
            pass
        finally:
            try:
                client.close()
            except:
                pass
            try:
                server.close()
            except:
                pass

    def is_running(self):
        return self.running and self.thread is not None and self.thread.is_alive()

    def stop(self):
        self.running = False
        self.thread = None


class SSHProxy:
    def __init__(self):
        self.process = None
        self.running = False
        self.http_proxy = HTTPProxy()
        self.http_proxy_started = False

    def start_ssh_tunnel(self):
        cmd = [
            "sshpass",
            "-p",
            PASSWORD,
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
            "-o",
            "BatchMode=no",
            "-D",
            f"0.0.0.0:{PROXY_PORT}",
            "-N",
            "-p",
            str(PORT),
            f"{USER}@{HOST}",
        ]
        log(f"Starting SSH tunnel: sshpass -p * ssh -D {PROXY_PORT} -N {USER}@{HOST}")
        self.process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return self.process

    def stop_ssh_tunnel(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    def run(self):
        self.running = True
        log("SSH SOCKS Proxy starting")

        while self.running:
            self.start_ssh_tunnel()
            time.sleep(2)

            if self.process and self.process.poll() is None:
                log(f"SSH tunnel active on 0.0.0.0:{PROXY_PORT}")
                if not self.http_proxy_started:
                    if self.http_proxy.start():
                        log(f"HTTP proxy active on 0.0.0.0:{HTTP_PROXY_PORT}")
                        self.http_proxy_started = True
            else:
                if self.process:
                    retcode = self.process.poll()
                    stderr = (
                        self.process.stderr.read().decode()
                        if self.process.stderr
                        else ""
                    )
                    log(f"SSH tunnel failed with code {retcode}: {stderr}")
                if self.http_proxy_started:
                    self.http_proxy.stop()
                    self.http_proxy_started = False
                log(f"Reconnecting in {RECONNECT_DELAY}s...")
                time.sleep(RECONNECT_DELAY)
                continue

            while self.running:
                if self.process and self.process.poll() is not None:
                    log("SSH tunnel lost, restarting...")
                    if self.http_proxy_started:
                        self.http_proxy.stop()
                        self.http_proxy_started = False
                    break
                time.sleep(1)

            self.stop_ssh_tunnel()

            if self.running:
                if self.http_proxy_started:
                    self.http_proxy.stop()
                    self.http_proxy_started = False
                log(f"Reconnecting in {RECONNECT_DELAY}s...")
                time.sleep(RECONNECT_DELAY)

        if self.http_proxy_started:
            self.http_proxy.stop()
        log("SSH SOCKS Proxy stopped")

    def shutdown(self):
        self.running = False
        if self.http_proxy_started:
            self.http_proxy.stop()
            self.http_proxy_started = False
        self.stop_ssh_tunnel()


if __name__ == "__main__":
    proxy = SSHProxy()

    def signal_handler(sig, frame):
        log("Received shutdown signal")
        proxy.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        proxy.run()
    except Exception as e:
        log(f"Error: {e}")
        proxy.shutdown()
        sys.exit(1)
