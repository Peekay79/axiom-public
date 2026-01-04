# utils/port_patch.py
import socket


def find_free_port(start_port=5000, max_tries=100):
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                return port
    raise RuntimeError("No free ports found")


if __name__ == "__main__":
    print(find_free_port())
