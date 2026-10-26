"""Local lifecycle tests; fake services and temporary folders, never the app DB."""

import importlib.util
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

HELPER = Path(__file__).resolve().parents[1] / "scripts/local_dev.py"
SPEC = importlib.util.spec_from_file_location("local_dev", HELPER)
local_dev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(local_dev)


def wait_until(condition, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.03)
    raise AssertionError("Timed out waiting for lifecycle condition")


def port_free(port):
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sipi-launcher-test-")
        self.root = Path(self.temp.name)
        self.supervisor = local_dev.Supervisor()
        self.runners = []

    def tearDown(self):
        self.supervisor.shutdown(grace_seconds=0.1)
        for runner in self.runners:
            if runner.poll() is None:
                runner.kill()
            runner.wait(timeout=3)
        local_dev.control_path(self.root).unlink(missing_ok=True)
        self.temp.cleanup()

    def free_port(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            return probe.getsockname()[1]

    def test_shutdown_releases_descendant_port_after_cli_parent_exits(self):
        port = self.free_port()
        child = (
            "import signal,socket,time; "
            "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
            f"s=socket.socket();s.bind(('127.0.0.1',{port}));s.listen();time.sleep(60)"
        )
        parent = f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{child!r}])"
        process = self.supervisor.start("fake-next", [sys.executable, "-c", parent])
        process.wait(timeout=3)
        wait_until(lambda: not port_free(port))
        started = time.monotonic()
        self.supervisor.shutdown(grace_seconds=0.2)
        wait_until(lambda: port_free(port))
        self.assertLess(time.monotonic() - started, 2)

    def test_occupied_port_does_not_stop_unrelated_listener(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            with self.assertRaisesRegex(RuntimeError, f"Порт {port}"):
                local_dev.check_ports((port,))
            self.assertFalse(port_free(port))

    def test_lock_prevents_second_start_and_keeps_active_socket(self):
        first = local_dev.Session(self.root)
        second = local_dev.Session(self.root)
        with patch.object(local_dev, "check_ports"):
            try:
                first.open()
                self.assertEqual(local_dev.control_path(self.root).stat().st_mode & 0o777, 0o600)
                with self.assertRaisesRegex(RuntimeError, "уже запускается"):
                    second.open()
                second.close()
                self.assertTrue(first.path.exists())
                self.assertEqual(local_dev.check(self.root), 1)
            finally:
                first.close()

    def fake_root(self, fail_frontend=False):
        backend = self.root / "backend"
        (backend / ".venv/bin").mkdir(parents=True)
        (backend / ".venv/bin/python").symlink_to(sys.executable)
        (self.root / "frontend").mkdir()
        (self.root / "bin").mkdir()
        port = self.free_port()
        service = """import os,pathlib,signal,subprocess,sys,time
root=pathlib.Path(os.environ["FAKE_ROOT"])
name="next" if pathlib.Path(sys.argv[0]).name=="node" else sys.argv[1]
if name=="migrate":
    (root/"migrated").touch();sys.exit(0)
(root/(name+".pid")).write_text(str(os.getpid()))
if name=="next":
    code="import socket,time; s=socket.socket();s.bind(('127.0.0.1',"+os.environ["FAKE_PORT"]+"));s.listen();time.sleep(60)"
    child=subprocess.Popen([sys.executable,"-c",code])
    (root/"descendant.pid").write_text(str(child.pid))
    if os.environ.get("FAIL_FRONTEND")=="yes":
        time.sleep(.5);sys.exit(12)
time.sleep(60)
"""
        (backend / "manage.py").write_text(service)
        node = self.root / "bin/node"
        node.write_text(f"#!{sys.executable}\n" + service)
        node.chmod(0o755)
        env = dict(os.environ)
        env.update(
            PATH=f"{self.root / 'bin'}:{os.environ['PATH']}",
            FAKE_ROOT=str(self.root),
            FAKE_PORT=str(port),
            FAIL_FRONTEND="yes" if fail_frontend else "no",
            ASSISTANT_IMAGES_ENABLED="false",
            SIPI_OLLAMA_BIN="",
        )
        return port, env

    def start_fake(self, fail_frontend=False, model_present=None):
        port, env = self.fake_root(fail_frontend)
        model_patch = ""
        if model_present is not None:
            ollama = self.root / "bin/ollama"
            ollama.write_text((self.root / "bin/node").read_text())
            ollama.chmod(0o755)
            env["SIPI_OLLAMA_BIN"] = str(ollama)
            env["ASSISTANT_OLLAMA_URL"] = "http://127.0.0.1:11434"
            model_patch = f"local_dev.model_available=lambda url:{model_present!r};"
        code = (
            f"import sys;sys.path.insert(0,{str(HELPER.parent)!r});"
            "import local_dev;from pathlib import Path;"
            "local_dev.check_ports=lambda:None;"
            + model_patch
            + f"sys.exit(local_dev.run(Path({str(self.root)!r})))"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", code],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.runners.append(process)
        wait_until(lambda: self.root.joinpath("descendant.pid").exists())
        wait_until(lambda: not port_free(port))
        return process, port

    def test_control_c_stops_full_session_and_socket(self):
        process, port = self.start_fake()
        process.send_signal(signal.SIGINT)
        self.assertEqual(process.wait(timeout=6), 0)
        wait_until(lambda: port_free(port))
        self.assertFalse(local_dev.control_path(self.root).exists())

    def test_terminal_hangup_stops_full_session(self):
        process, port = self.start_fake()
        process.send_signal(signal.SIGHUP)
        self.assertEqual(process.wait(timeout=6), 0)
        wait_until(lambda: port_free(port))
        self.assertFalse(local_dev.control_path(self.root).exists())

    def test_stop_command_is_scoped_and_idempotent(self):
        process, port = self.start_fake()
        unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"])
        self.runners.append(unrelated)
        self.assertEqual(local_dev.stop(self.root), 0)
        self.assertEqual(process.wait(timeout=3), 0)
        self.assertIsNone(unrelated.poll())
        self.assertEqual(local_dev.stop(self.root), 0)
        wait_until(lambda: port_free(port))

    def test_failed_frontend_stops_other_services_and_descendant(self):
        process, port = self.start_fake(fail_frontend=True)
        self.assertEqual(process.wait(timeout=6), 12)
        wait_until(lambda: port_free(port))
        for name in ("assistant_worker", "runserver"):
            pid = int((self.root / f"{name}.pid").read_text())
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_port_failure_prevents_migrations(self):
        with patch.object(local_dev, "check_ports", side_effect=RuntimeError("occupied port")):
            self.assertEqual(local_dev.run(self.root), 1)
        self.assertFalse((self.root / "migrated").exists())
        self.assertFalse(local_dev.control_path(self.root).exists())

    def test_owned_model_process_stops_with_session(self):
        process, _ = self.start_fake(model_present=False)
        wait_until(lambda: (self.root / "serve.pid").exists())
        pid = int((self.root / "serve.pid").read_text())
        self.assertEqual(local_dev.stop(self.root), 0)
        process.wait(timeout=3)
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_existing_model_service_is_reused_without_starting_owned_one(self):
        process, _ = self.start_fake(model_present=True)
        self.assertFalse((self.root / "serve.pid").exists())
        self.assertEqual(local_dev.stop(self.root), 0)
        process.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
