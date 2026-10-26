#!/usr/bin/env python3
"""Run and stop this checkout's local services without leaving child processes."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
import selectors
import signal
import socket
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def control_path(root: Path) -> Path:
    digest = hashlib.sha256(os.fsencode(root.resolve())).hexdigest()[:16]
    return Path("/tmp") / f"sipi-dev-{os.getuid()}-{digest}.sock"


def group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Supervisor:
    """Own whole process groups; a finished CLI can still have live descendants."""

    def __init__(self) -> None:
        self.processes: dict[int, tuple[str, subprocess.Popen]] = {}

    def start(
        self,
        name: str,
        args: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        stdout=None,
    ) -> subprocess.Popen:
        process = subprocess.Popen(
            args,
            cwd=cwd,
            env=env,
            stdout=stdout,
            stderr=subprocess.STDOUT if stdout is not None else None,
            start_new_session=True,
        )
        self.processes[process.pid] = (name, process)
        return process

    def poll_running(self) -> None:
        for pgid, (_, process) in list(self.processes.items()):
            if process.poll() is not None and not group_exists(pgid):
                del self.processes[pgid]

    def shutdown(self, grace_seconds: float = 3) -> None:
        self.poll_running()
        for pgid in self.processes:
            try:
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + grace_seconds
        while self.processes and time.monotonic() < deadline:
            self.poll_running()
            if self.processes:
                time.sleep(0.05)
        for pgid in self.processes:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for _, process in self.processes.values():
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
        self.processes.clear()


def check_ports(ports: tuple[int, ...] = (3000, 8000)) -> None:
    problems = []
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as error:
                pids = ""
                try:
                    result = subprocess.run(
                        ["lsof", "-nP", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
                        capture_output=True,
                        text=True,
                        timeout=1,
                        check=False,
                    )
                    pids = ", ".join(dict.fromkeys(result.stdout.split()))
                except (OSError, subprocess.TimeoutExpired):
                    pass
                owner = f" (PID {pids})" if pids else ""
                problems.append(f"Порт {port} недоступен{owner}: {error.strerror}.")
    if problems:
        raise RuntimeError(
            "\n".join(problems)
            + "\nЕсли это Сипи, выполните ./stop.sh. Если сервер запущен отдельно, "
            "остановите его через Control + C в его терминале."
        )


def check(root: Path = ROOT) -> int:
    """Cheap shell preflight; run() repeats this while holding the run lock."""
    runtime = root / ".runtime"
    runtime.mkdir(exist_ok=True)
    try:
        with (runtime / "local-dev.lock").open("a+") as lock:
            os.fchmod(lock.fileno(), 0o600)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError(
                    "Сипи уже запускается или работает из этой папки. "
                    "Для остановки выполните ./stop.sh."
                ) from error
            check_ports()
        return 0
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


class Session:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = control_path(root)
        self.lock = None
        self.server = None
        self.socket_bound = False
        self.selector = selectors.DefaultSelector()
        self.stop_requested = False
        self.supervisor = Supervisor()

    def open(self) -> None:
        runtime = self.root / ".runtime"
        runtime.mkdir(exist_ok=True)
        self.lock = (runtime / "local-dev.lock").open("a+")
        os.fchmod(self.lock.fileno(), 0o600)
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(
                "Сипи уже запускается или работает из этой папки. "
                "Для остановки выполните ./stop.sh."
            ) from error
        check_ports()
        if self.path.exists() or self.path.is_symlink():
            existing = self.path.lstat()
            if existing.st_uid != os.getuid() or not stat.S_ISSOCK(existing.st_mode):
                raise RuntimeError(f"Не удалось создать канал управления: {self.path}")
            self.path.unlink()
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(self.path))
        self.socket_bound = True
        os.chmod(self.path, 0o600)
        self.server.listen(4)
        self.server.setblocking(False)
        self.selector.register(self.server, selectors.EVENT_READ)

    def poll(self, timeout: float = 0.2) -> None:
        for key, _ in self.selector.select(timeout):
            connection, _ = key.fileobj.accept()
            with connection:
                connection.settimeout(0.2)
                try:
                    if connection.recv(32).strip() == b"stop":
                        self.stop_requested = True
                        connection.sendall(b"stopping\n")
                except (OSError, TimeoutError):
                    pass
        self.supervisor.poll_running()

    def wait_for(self, process: subprocess.Popen) -> int | None:
        while process.poll() is None and not self.stop_requested:
            self.poll()
        return process.poll()

    def close(self) -> None:
        self.supervisor.shutdown()
        if self.server is not None:
            try:
                self.selector.unregister(self.server)
            except KeyError:
                pass
            self.server.close()
        if self.socket_bound:
            self.path.unlink(missing_ok=True)
        self.selector.close()
        if self.lock is not None:
            self.lock.close()


def model_available(url: str) -> bool:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=2):
            return True
    except (OSError, urllib.error.URLError):
        return False


def run(root: Path = ROOT) -> int:
    session = Session(root)
    previous_handlers = {}

    def request_stop(_signum, _frame):
        session.stop_requested = True

    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        previous_handlers[signum] = signal.signal(signum, request_stop)
    try:
        session.open()
        python = str(root / "backend/.venv/bin/python")
        migration = session.supervisor.start(
            "migrate", [python, "backend/manage.py", "migrate", "--noinput"], cwd=root
        )
        code = session.wait_for(migration)
        if session.stop_requested:
            return 0
        if code:
            print("Не удалось применить миграции. Сипи не запущен.", file=sys.stderr)
            return code
        if os.environ.get("SIPI_OLLAMA_BIN"):
            url = os.environ.get("ASSISTANT_OLLAMA_URL", "http://127.0.0.1:11434")
            if url.rstrip("/") == "http://127.0.0.1:11434" and not model_available(url):
                model_env = dict(os.environ)
                model_env.update(
                    OLLAMA_HOST="127.0.0.1:11434",
                    OLLAMA_MODELS=str(root / ".runtime/models"),
                    OLLAMA_NO_CLOUD="1",
                )
                with (root / ".runtime/ollama.log").open("a") as output:
                    session.supervisor.start(
                        "ollama",
                        [os.environ["SIPI_OLLAMA_BIN"], "serve"],
                        cwd=root,
                        env=model_env,
                        stdout=output,
                    )
        session.supervisor.start(
            "chat", [python, "backend/manage.py", "assistant_worker", "--kind", "chat"], cwd=root
        )
        if os.environ.get("ASSISTANT_IMAGES_ENABLED", "false") == "true":
            session.supervisor.start(
                "logo",
                [python, "backend/manage.py", "assistant_worker", "--kind", "logo"],
                cwd=root,
            )
        backend = session.supervisor.start(
            "django",
            [python, "backend/manage.py", "runserver", "127.0.0.1:8000", "--noreload"],
            cwd=root,
        )
        frontend = session.supervisor.start(
            "next",
            [
                "node",
                "node_modules/next/dist/bin/next",
                "dev",
                "--hostname",
                "127.0.0.1",
                "--port",
                "3000",
            ],
            cwd=root / "frontend",
        )
        print("Сипи: http://127.0.0.1:3000 · Админка: http://127.0.0.1:8000/admin/", flush=True)
        print("Остановка: Control + C в этом терминале или ./stop.sh в другом.", flush=True)
        if os.environ.get("EMAIL_BACKEND") == "django.core.mail.backends.console.EmailBackend":
            print("Коды подтверждения появятся ниже, в выводе Django.", flush=True)
        else:
            print("Доставка кодов подтверждения настроена через EMAIL_BACKEND.", flush=True)
        while not session.stop_requested:
            for process, name in ((backend, "Django"), (frontend, "Next.js")):
                code = process.poll()
                if code is not None:
                    print(
                        f"{name} завершился (код {code}). Останавливаю остальные части Сипи.",
                        file=sys.stderr,
                    )
                    return code or 1
            session.poll()
        return 0
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        session.close()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def stop(root: Path = ROOT, timeout: float = 10) -> int:
    path = control_path(root)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        try:
            client.connect(str(path))
        except (FileNotFoundError, ConnectionRefusedError):
            print("Управляемый запуск Сипи из этой папки уже остановлен.")
            return 0
        except OSError as error:
            print(f"Не удалось связаться с запущенным Сипи: {error}", file=sys.stderr)
            return 1
        try:
            client.sendall(b"stop\n")
            if client.recv(32).strip() != b"stopping":
                raise RuntimeError("Не получено подтверждение остановки Сипи.")
        except (OSError, RuntimeError) as error:
            print(f"Не удалось остановить Сипи: {error}", file=sys.stderr)
            return 1
    deadline = time.monotonic() + timeout
    while path.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    if path.exists():
        print("Сипи ещё останавливается. Проверьте терминал запуска.", file=sys.stderr)
        return 1
    print("Сипи остановлен.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "run", "stop"))
    args = parser.parse_args()
    if args.command == "check":
        return check()
    return run() if args.command == "run" else stop()


if __name__ == "__main__":
    raise SystemExit(main())
