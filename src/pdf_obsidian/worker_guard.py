"""Watchdog em outro processo, independente do GIL do parser PDF."""
import argparse
import os
import math
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time


class GuardedCommands:
    def __init__(self, commands, *, timeout=3600, memory_limit=2 * 1024**3,
                 workspace=None, disk_limit=2 * 1024**3):
        self.commands, self.timeout = commands, timeout
        command = [sys.executable, '-m', 'pdf_obsidian.worker_guard', '--pid', str(os.getpid()),
                   '--memory-limit', str(memory_limit), '--disk-limit', str(disk_limit)]
        if workspace:
            command += ['--workspace', str(workspace)]
        self.monitor = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                        close_fds=True)

    def get(self):
        self.monitor.stdin.write(b'0\n')
        self.monitor.stdin.flush()
        command = self.commands.get()
        import resource
        consumed = resource.getrusage(resource.RUSAGE_SELF)
        # Limite de CPU por comando no kernel, inclusive durante retenção do GIL.
        _, hard = resource.getrlimit(resource.RLIMIT_CPU)
        soft = math.ceil(consumed.ru_utime + consumed.ru_stime) + 300
        if hard != resource.RLIM_INFINITY:
            soft = min(soft, hard)
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
        timeout = min(30, self.timeout) if command[0] == 'render' else self.timeout
        self.monitor.stdin.write(f'{time.monotonic() + timeout}\n'.encode())
        self.monitor.stdin.flush()
        return command


def usage(workspace):
    total = 0
    if workspace:
        for folder, dirs, files in os.walk(workspace, followlinks=False):
            for name in files:
                try:
                    total += (Path(folder) / name).lstat().st_size
                except FileNotFoundError:
                    pass  # Escrita/limpeza concorrente normal da sessão.
    return total


def monitor(pid, memory_limit, disk_limit, workspace):
    # O pipe fecha quando o worker morre: o monitor não fica órfão.
    selector = selectors.DefaultSelector()
    selector.register(sys.stdin.buffer, selectors.EVENT_READ)
    deadline = 0
    buffer = b''
    while True:
        if selector.select(.1):
            data = os.read(sys.stdin.fileno(), 4096)
            if not data:
                return
            buffer += data
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                deadline = float(line)
        try:
            status = Path(f'/proc/{pid}/status').read_text()
            rss = next(int(line.split()[1]) * 1024 for line in status.splitlines()
                       if line.startswith('VmRSS:'))
            disk = usage(workspace)
        except (OSError, StopIteration):
            # Não continuar processamento sem supervisão verificável.
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            return
        if rss > memory_limit or disk > disk_limit or (deadline and time.monotonic() > deadline):
            os.kill(pid, signal.SIGKILL)
            return


def guard_commands(commands, workspace=None):
    import resource
    resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024**2, 256 * 1024**2))
    return GuardedCommands(commands, workspace=workspace)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--memory-limit', type=int, required=True)
    parser.add_argument('--disk-limit', type=int, required=True)
    parser.add_argument('--workspace', type=Path)
    args = parser.parse_args()
    monitor(args.pid, args.memory_limit, args.disk_limit, args.workspace)
