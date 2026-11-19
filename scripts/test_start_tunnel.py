"""Check tunnel orchestration without starting a public tunnel or changing Docker."""

import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import call, MagicMock, patch


filename = Path(__file__).with_name("start-tunnel.py")
spec = importlib.util.spec_from_file_location("start_tunnel", filename)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

url_filename = filename.with_name("set-public-url.py")
url_spec = importlib.util.spec_from_file_location("set_public_url", url_filename)
url_module = importlib.util.module_from_spec(url_spec)
url_spec.loader.exec_module(url_module)


class NgrokTunnelTests(unittest.TestCase):
    def make_tunnel(self, output):
        process = MagicMock()
        process.stdout = io.StringIO(output)
        process.poll.return_value = None

        with patch.object(module.subprocess, "Popen", return_value=process) as start:
            tunnel = module.NgrokTunnel("ngrok", "http://127.0.0.1:80")
            tunnel.start()

        self.addCleanup(tunnel.stop)

        return tunnel, process, start.call_args.args[0]

    def test_command_uses_ngrok_json_logs(self):
        _, _, command = self.make_tunnel("")

        self.assertEqual(command[:3], ["ngrok", "http", "http://127.0.0.1:80"])
        self.assertEqual(command[command.index("--log-format") + 1], "json")
        self.assertIn("--inspect=false", command)

    def test_url_is_detected_only_when_endpoint_starts(self):
        output = json.dumps({"msg": "session established"}) + "\n"
        output += json.dumps({"msg": "started tunnel", "url": "https://demo.ngrok-free.app"}) + "\n"
        tunnel, _, _ = self.make_tunnel(output)

        self.assertEqual(tunnel.wait_url(1), "https://demo.ngrok-free.app")

    def test_endpoint_event_supports_custom_domains(self):
        output = json.dumps({"msg": "started endpoint", "url": "https://demo.example.com:443/"}) + "\n"
        tunnel, _, _ = self.make_tunnel(output)

        self.assertEqual(tunnel.wait_url(1), "https://demo.example.com")

    def test_unrelated_urls_are_not_accepted(self):
        output = json.dumps({"msg": "connecting", "url": "https://demo.ngrok-free.app"}) + "\n"
        tunnel, _, _ = self.make_tunnel(output)

        with self.assertRaisesRegex(RuntimeError, "authtoken"):
            tunnel.wait_url(1)

    def test_http_endpoint_is_not_accepted(self):
        output = json.dumps({"msg": "started tunnel", "url": "http://demo.ngrok-free.app"}) + "\n"
        tunnel, _, _ = self.make_tunnel(output)

        with self.assertRaises(RuntimeError):
            tunnel.wait_url(1)

    def test_malformed_urls_and_logs_are_ignored(self):
        lines = [
            "not JSON", "[]",
            json.dumps({"msg": "started tunnel", "url": "https://[invalid"}),
            json.dumps({"msg": "started tunnel", "url": "https://demo.ngrok-free.app/path"}),
            json.dumps({"msg": "started tunnel", "url": "https://demo.ngrok-free.app:invalid"}),
        ]
        tunnel, _, _ = self.make_tunnel("\n".join(lines))

        with self.assertRaises(RuntimeError):
            tunnel.wait_url(1)

    def test_wait_url_has_a_timeout(self):
        tunnel = module.NgrokTunnel("ngrok", "http://127.0.0.1:80")

        with self.assertRaisesRegex(RuntimeError, "443/TCP"):
            tunnel.wait_url(0.01)

    def test_stop_kills_process_if_termination_times_out(self):
        tunnel = module.NgrokTunnel("ngrok", "http://127.0.0.1:80")
        process = MagicMock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("ngrok", 10), 0]
        tunnel.process = process

        tunnel.stop()

        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_args_list, [call(timeout=10), call(timeout=5)])


class PublicReadinessTests(unittest.TestCase):
    def test_public_origin_is_checked_before_announcing_links(self):
        tunnel = MagicMock()
        tunnel.process.poll.return_value = None
        status_response = MagicMock()
        status_response.__enter__.return_value.status = 200
        metadata_response = MagicMock()
        metadata_response.__enter__.return_value.read.return_value = json.dumps({
            "issuer": "https://demo.ngrok-free.app/authentik/application/o/rallly/"
        })

        with patch.object(module, "urlopen", side_effect=[status_response, metadata_response]) as open_url:
            module.wait_ready(tunnel, "https://demo.ngrok-free.app", 1)

        self.assertEqual(open_url.call_count, 2)

        for request in open_url.call_args_list:
            self.assertEqual(request.args[0].get_header("Ngrok-skip-browser-warning"), "true")

        self.assertEqual(open_url.call_args_list[0].args[0].full_url, "https://demo.ngrok-free.app/api/status")
        self.assertEqual(
            open_url.call_args_list[1].args[0].full_url,
            "https://demo.ngrok-free.app/authentik/application/o/rallly/.well-known/openid-configuration",
        )

    def test_dead_tunnel_is_rejected(self):
        tunnel = MagicMock()
        tunnel.process.poll.return_value = 1

        with self.assertRaisesRegex(RuntimeError, "arrêté"):
            module.wait_ready(tunnel, "https://demo.ngrok-free.app", 1)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.root = filename.resolve().parents[1]
        self.tunnel = MagicMock()
        self.tunnel.wait_url.return_value = "https://demo.ngrok-free.app"
        self.tunnel.process.poll.return_value = None
        self.tunnel.wait.side_effect = KeyboardInterrupt
        self.apply = MagicMock()
        self.ready = MagicMock()
        patches = [
            patch.object(module.shutil, "which", return_value="/usr/bin/ngrok"),
            patch.object(module.Path, "is_file", return_value=True),
            patch.object(module, "read_configuration", return_value=("http://127.0.0.1:80", "http://rallly.localhost")),
            patch.object(module, "NgrokTunnel", return_value=self.tunnel),
            patch.object(module, "apply_public_url", self.apply),
            patch.object(module, "wait_ready", self.ready),
            patch.object(module.subprocess, "run"),
            patch("builtins.print"),
        ]

        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def test_ctrl_c_stops_tunnel_and_restores_previous_origin(self):
        self.assertEqual(module.main([]), 0)
        self.assertEqual(self.apply.call_args_list, [
            call(self.root, "https://demo.ngrok-free.app", email_login=False),
            call(self.root, "http://rallly.localhost"),
        ])
        self.tunnel.stop.assert_called_once()

    def test_email_login_is_enabled_only_for_the_public_session(self):
        self.assertEqual(module.main(["--email-login"]), 0)
        self.assertEqual(self.apply.call_args_list, [
            call(self.root, "https://demo.ngrok-free.app", email_login=True),
            call(self.root, "http://rallly.localhost"),
        ])
        self.tunnel.stop.assert_called_once()

    def test_failed_email_configuration_restores_the_base_configuration(self):
        self.apply.side_effect = [subprocess.CalledProcessError(1, "configuration"), None]

        self.assertEqual(module.main(["--email-login"]), 1)
        self.assertEqual(self.apply.call_args_list[-1], call(self.root, "http://rallly.localhost"))

    def test_failed_configuration_also_restores_previous_origin(self):
        self.apply.side_effect = [subprocess.CalledProcessError(1, "configuration"), None]

        self.assertEqual(module.main([]), 1)
        self.assertEqual(self.apply.call_count, 2)
        self.tunnel.stop.assert_called_once()

    def test_missing_url_does_not_change_configuration(self):
        self.tunnel.wait_url.side_effect = RuntimeError("URL absente")

        self.assertEqual(module.main([]), 1)
        self.apply.assert_not_called()
        self.tunnel.stop.assert_called_once()

    def test_failed_public_check_restores_previous_origin(self):
        self.ready.side_effect = RuntimeError("Émetteur OIDC incorrect")

        self.assertEqual(module.main([]), 1)
        self.assertEqual(self.apply.call_count, 2)
        self.tunnel.stop.assert_called_once()

    def test_restore_failure_returns_nonzero_status(self):
        self.apply.side_effect = [None, subprocess.CalledProcessError(1, "restore")]

        self.assertEqual(module.main([]), 1)
        self.tunnel.stop.assert_called_once()


class EmailConfigurationTests(unittest.TestCase):
    def test_launcher_passes_email_option_to_url_script(self):
        root = filename.resolve().parents[1]

        with patch.object(module.subprocess, "run") as run:
            module.apply_public_url(root, "https://demo.ngrok-free.app", email_login=True)

        self.assertEqual(run.call_args.args[0][-2:], ["https://demo.ngrok-free.app", "--email-login"])

    def test_overlay_is_used_for_validation_startup_and_authentik(self):
        compose = ["docker", "compose", "-f", "docker-compose.yaml", "-f", "docker-compose.email.yaml"]

        with (
            patch.object(url_module.Path, "is_file", return_value=True),
            patch.object(url_module, "update_environment"),
            patch.object(url_module.subprocess, "run") as run,
            patch.object(url_module, "configure_authentik") as configure,
            patch("builtins.print"),
        ):
            url_module.main(["http://rallly.localhost", "--email-login"])

        self.assertEqual(run.call_args_list[0].args[0], [*compose, "config", "--quiet"])
        self.assertEqual(run.call_args_list[1].args[0], [*compose, "up", "-d", "--wait", "--wait-timeout", "240"])
        self.assertEqual(configure.call_args.args[1], compose)

    def test_default_configuration_excludes_email_overlay(self):
        with (
            patch.object(url_module.Path, "is_file", return_value=True),
            patch.object(url_module, "update_environment"),
            patch.object(url_module.subprocess, "run") as run,
            patch.object(url_module, "configure_authentik"),
            patch("builtins.print"),
        ):
            url_module.main(["http://rallly.localhost"])

        for invocation in run.call_args_list:
            self.assertNotIn("docker-compose.email.yaml", invocation.args[0])


if __name__ == "__main__":
    unittest.main()
