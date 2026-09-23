"""Credential boundaries of the local launcher; no server or paid API calls."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
import warnings
from unittest.mock import patch


class FakeProcess:
    pid = 4320

    def __init__(self, command, returncode):
        self.args = command
        self.returncode = returncode

    def wait(self, timeout=None):
        return self.returncode


class LiveLauncherTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'start_live.py'
        self.assertTrue(path.is_file(), 'The secure live launcher must exist')
        spec = importlib.util.spec_from_file_location('winx_live_launcher', path)
        self.launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.launcher)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        runtime = self.root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        runtime.parent.mkdir(parents=True)
        runtime.touch()

    def test_secret_reaches_child_environment_only_and_exit_code_is_preserved(self):
        fake_key = 'dummy-secret-for-offline-test'
        captured = {}
        before_env = dict(os.environ)
        before_files = set(self.root.rglob('*'))

        def launch(command, **kwargs):
            captured.update(command=command, env=dict(kwargs['env']), cwd=kwargs['cwd'],
                            popen_kwargs=kwargs)
            return FakeProcess(command, 7)

        output = io.StringIO()
        with patch.object(self.launcher, 'ROOT', self.root), \
             patch('sys.stdin.isatty', return_value=True), \
             patch.object(self.launcher.getpass, 'getpass', return_value=fake_key), \
             patch.object(self.launcher.subprocess, 'Popen', side_effect=launch), \
             patch.object(self.launcher.subprocess, 'run', return_value=subprocess.CompletedProcess([], 7)), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = self.launcher.main(['--model', 'test-model', '--port', '8515', '--headless'])

        self.assertEqual(code, 7)
        self.assertEqual(captured['env']['OPENAI_API_KEY'], fake_key)
        self.assertEqual(captured['env']['OPENAI_MODEL'], 'test-model')
        self.assertEqual(captured['env']['DEMO_MODE'], '0')
        if os.name == 'nt':
            self.assertEqual(captured['popen_kwargs']['creationflags'],
                             subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            self.assertTrue(captured['popen_kwargs']['start_new_session'])
        self.assertIn('--server.address=127.0.0.1', captured['command'])
        self.assertIn('--server.port=8515', captured['command'])
        self.assertNotIn(fake_key, ' '.join(captured['command']))
        self.assertNotIn(fake_key, output.getvalue())
        self.assertEqual(dict(os.environ), before_env)
        self.assertEqual(set(self.root.rglob('*')), before_files)

    def test_ctrl_c_interrupts_child_then_force_stops_only_its_tree_on_timeout(self):
        fake_key = 'dummy-secret-for-offline-test'
        captured = {}

        class SlowProcess:
            pid = 4321
            returncode = 0

            def __init__(self, command):
                self.args = command
                self.wait_calls = 0
                self.signals = []

            def wait(self, timeout=None):
                self.wait_calls += 1
                if self.wait_calls == 1:
                    raise KeyboardInterrupt
                if self.wait_calls == 2:
                    raise KeyboardInterrupt
                raise subprocess.TimeoutExpired(self.args, timeout)

            def send_signal(self, sig):
                self.signals.append(sig)

        process = None

        def launch(command, **kwargs):
            nonlocal process
            process = SlowProcess(command)
            captured.update(command=command, env=dict(kwargs['env']))
            return process

        output = io.StringIO()
        with patch.object(self.launcher, 'ROOT', self.root), \
             patch('sys.stdin.isatty', return_value=True), \
             patch.object(self.launcher.getpass, 'getpass', return_value=fake_key), \
             patch.object(self.launcher.subprocess, 'Popen', side_effect=launch), \
             patch.object(self.launcher.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run, \
             patch.object(self.launcher.os, 'killpg', create=True) as killpg, \
             patch.object(self.launcher, '_signal_process_group') as signal_group, \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = self.launcher.main(['--model', 'test-model'])

        self.assertEqual(code, 130)
        self.assertEqual(process.wait_calls, 4)
        signal_group.assert_called_once_with(process)
        if os.name == 'nt':
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][-4:], ['/PID', '4321', '/T', '/F'])
            self.assertNotIn(fake_key, ' '.join(run.call_args.args[0]))
        else:
            run.assert_not_called()
            killpg.assert_called_once_with(4321, signal.SIGKILL)
        self.assertNotIn(fake_key, output.getvalue())

    def test_ctrl_c_waits_for_graceful_child_exit_without_forced_kill(self):
        class GracefulProcess(FakeProcess):
            def __init__(self, command, returncode):
                super().__init__(command, returncode)
                self.wait_calls = 0

            def wait(self, timeout=None):
                self.wait_calls += 1
                if self.wait_calls == 1:
                    raise KeyboardInterrupt
                return 0

        process = None

        def launch(command, **kwargs):
            nonlocal process
            process = GracefulProcess(command, 0)
            return process

        with patch.object(self.launcher, 'ROOT', self.root), \
             patch('sys.stdin.isatty', return_value=True), \
             patch.object(self.launcher.getpass, 'getpass', return_value='fake-key'), \
             patch.object(self.launcher.subprocess, 'Popen', side_effect=launch), \
             patch.object(self.launcher, '_signal_process_group') as signal_group, \
             patch.object(self.launcher.subprocess, 'run') as run, \
             contextlib.redirect_stdout(io.StringIO()):
            code = self.launcher.main(['--model', 'test-model'])

        self.assertEqual(code, 130)
        self.assertEqual(process.wait_calls, 2)
        signal_group.assert_called_once_with(process)
        run.assert_not_called()

    def test_main_wait_timeout_then_ctrl_c_enters_cleanup(self):
        class InterruptAfterPolling(FakeProcess):
            def __init__(self, command, returncode):
                super().__init__(command, returncode)
                self.wait_timeouts = []
                self.wait_calls = 0

            def wait(self, timeout=None):
                self.wait_calls += 1
                self.wait_timeouts.append(timeout)
                if self.wait_calls == 1:
                    raise subprocess.TimeoutExpired(self.args, timeout)
                if self.wait_calls == 2:
                    raise KeyboardInterrupt
                return 0

        process = None

        def launch(command, **kwargs):
            nonlocal process
            process = InterruptAfterPolling(command, 0)
            return process

        with patch.object(self.launcher, 'ROOT', self.root), \
             patch('sys.stdin.isatty', return_value=True), \
             patch.object(self.launcher.getpass, 'getpass', return_value='fake-key'), \
             patch.object(self.launcher.subprocess, 'Popen', side_effect=launch), \
             patch.object(self.launcher, '_signal_process_group') as signal_group, \
             patch.object(self.launcher.subprocess, 'run') as run, \
             contextlib.redirect_stdout(io.StringIO()):
            code = self.launcher.main(['--model', 'test-model'])

        self.assertEqual(code, 130)
        self.assertEqual(process.wait_calls, 3)
        self.assertEqual(process.wait_timeouts[0], self.launcher.WAIT_POLL_SECONDS)
        signal_group.assert_called_once_with(process)
        run.assert_not_called()

    def test_redirected_input_is_rejected_before_reading_credentials(self):
        with patch.object(self.launcher, 'ROOT', self.root), \
             patch('sys.stdin.isatty', return_value=False), \
             patch.object(self.launcher.getpass, 'getpass', side_effect=AssertionError('Must not prompt')), \
             patch.object(self.launcher.subprocess, 'Popen', side_effect=AssertionError('Must not launch')), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                self.launcher.main(['--model', 'test-model'])
        self.assertEqual(error.exception.code, 2)

    def test_empty_key_does_not_start_server(self):
        with patch.object(self.launcher, 'ROOT', self.root), \
             patch('sys.stdin.isatty', return_value=True), \
             patch.object(self.launcher.getpass, 'getpass', return_value='  '), \
             patch.object(self.launcher.subprocess, 'Popen', side_effect=AssertionError('Must not launch')), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                self.launcher.main(['--model', 'test-model'])
        self.assertEqual(error.exception.code, 2)

    def test_unavailable_hidden_input_never_falls_back_to_echo(self):
        def unavailable_input(prompt):
            warnings.warn('Hidden input unavailable', self.launcher.getpass.GetPassWarning)
            self.fail('Visible-input fallback must not run')

        with patch.object(self.launcher, 'ROOT', self.root), \
             patch('sys.stdin.isatty', return_value=True), \
             patch.object(self.launcher.getpass, 'getpass', side_effect=unavailable_input), \
             patch.object(self.launcher.subprocess, 'Popen', side_effect=AssertionError('Must not launch')), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                self.launcher.main(['--model', 'test-model'])
        self.assertEqual(error.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
