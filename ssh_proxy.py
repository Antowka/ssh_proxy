#!/usr/bin/env python3

import subprocess
import time
import signal
import os
import sys

HOST = "example.com"
PORT = 22
USER = "root"
PASSWORD = "Passw0rd"
PROXY_PORT = 8787
RECONNECT_DELAY = 5

LOG_FILE = "/opt/ssh_proxy/ssh-proxy.log"

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} - {msg}\n"
    with open(LOG_FILE, "a") as f:
        f.write(line)
    print(line.strip())

class SSHProxy:
    def __init__(self):
        self.process = None
        self.running = False

    def start_ssh_tunnel(self):
        cmd = [
            "sshpass", "-p", PASSWORD,
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-o", "BatchMode=no",
            "-D", f"0.0.0.0:{PROXY_PORT}",
            "-N",
            "-p", str(PORT),
            f"{USER}@{HOST}"
        ]
        log(f"Starting SSH tunnel: sshpass -p * ssh -D {PROXY_PORT} -N {USER}@{HOST}")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
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
            else:
                if self.process:
                    retcode = self.process.poll()
                    stderr = self.process.stderr.read().decode() if self.process.stderr else ""
                    log(f"SSH tunnel failed with code {retcode}: {stderr}")
                log(f"Reconnecting in {RECONNECT_DELAY}s...")
                time.sleep(RECONNECT_DELAY)
                continue

            while self.running:
                if self.process and self.process.poll() is not None:
                    log("SSH tunnel lost, restarting...")
                    break
                time.sleep(1)

            self.stop_ssh_tunnel()

            if self.running:
                log(f"Reconnecting in {RECONNECT_DELAY}s...")
                time.sleep(RECONNECT_DELAY)

        log("SSH SOCKS Proxy stopped")

    def shutdown(self):
        self.running = False
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
