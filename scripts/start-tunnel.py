"""Lancer ngrok et configurer automatiquement les URL de Rallly et Authentik."""

import argparse
from collections import deque
import json
from pathlib import Path
from queue import Empty, Queue
import shutil
import subprocess
import sys
from threading import Thread
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit


class NgrokTunnel:
    def __init__(self, executable: str, origin: str, verbose: bool = False):
        self.executable = executable
        self.origin = origin
        self.verbose = verbose
        self.process: subprocess.Popen[str] | None = None
        self.reader: Thread | None = None
        self.urls: Queue[str | None] = Queue()
        self.logs: deque[str] = deque(maxlen=20)

    def start(self):
        self.process = subprocess.Popen(
            [
                self.executable, "http", self.origin,
                "--log", "stdout", "--log-format", "json", "--log-level", "info",
                "--inspect=false",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        self.reader = Thread(target=self.read_output, daemon=True)
        self.reader.start()

    def read_output(self):
        if self.process is None or self.process.stdout is None:
            return

        for line in self.process.stdout:
            self.logs.append(line.rstrip())

            if self.verbose:
                print(line, end="", flush=True)

            url = self.read_public_url(line)

            if url is not None:
                self.urls.put(url)

        self.urls.put(None)

    @staticmethod
    def read_public_url(line: str) -> str | None:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return None

        if not isinstance(event, dict) or event.get("msg") not in ("started tunnel", "started endpoint"):
            return None

        value = event.get("url")

        if not isinstance(value, str):
            return None

        try:
            url = urlsplit(value)
            port = url.port
        except ValueError:
            return None

        if url.scheme != "https" or not url.hostname or port not in (None, 443):
            return None

        if url.path not in ("", "/") or url.query or url.fragment or url.username or url.password:
            return None

        host = url.hostname

        if ":" in host:
            host = f"[{host}]"

        return f"https://{host}"

    def wait_url(self, timeout: float) -> str:
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()

            try:
                url = self.urls.get(timeout=max(remaining, 0.001))
            except Empty:
                break

            if url is None:
                raise RuntimeError("ngrok s'est arrêté avant de fournir une URL HTTPS ; vérifier son authtoken et ses logs")

            return url

        raise RuntimeError("Délai dépassé en attendant la connexion ngrok ; vérifier l'accès à ngrok sur 443/TCP")

    def wait(self) -> int:
        if self.process is None:
            raise RuntimeError("Le tunnel n'a pas démarré")

        return self.process.wait()

    def stop(self):
        if self.process is None:
            return

        if self.process.poll() is None:
            self.process.terminate()

            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

        if self.reader is not None:
            self.reader.join(timeout=1)

        if self.process.stdout is not None:
            self.process.stdout.close()


def read_configuration(root: Path) -> tuple[str, str]:
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    config = json.loads(result.stdout)
    traefik = config["services"]["traefik"]
    port = traefik["ports"][0]["published"]
    previous_origin = traefik["environment"]["PUBLIC_BASE_URL"]

    return f"http://127.0.0.1:{port}", previous_origin


def apply_public_url(root: Path, origin: str, email_login: bool = False):
    command = [sys.executable, str(root / "scripts" / "set-public-url.py"), origin]

    if email_login:
        command.append("--email-login")

    subprocess.run(
        command,
        cwd=root,
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    )


def wait_ready(tunnel: NgrokTunnel, origin: str, timeout: float):
    deadline = time.monotonic() + timeout
    last_error = None

    while time.monotonic() < deadline:
        if tunnel.process is None or tunnel.process.poll() is not None:
            raise RuntimeError("ngrok s'est arrêté pendant la vérification publique")

        try:
            headers = {
                "User-Agent": "Rallly-tunnel-check",
                "ngrok-skip-browser-warning": "true",
            }
            request = Request(f"{origin}/api/status", headers=headers)

            with urlopen(request, timeout=5) as response:
                if response.status != 200:
                    raise ValueError("Rallly ne répond pas correctement")

            discovery = Request(
                f"{origin}/authentik/application/o/rallly/.well-known/openid-configuration",
                headers=headers,
            )

            with urlopen(discovery, timeout=5) as response:
                metadata = json.load(response)

            if metadata.get("issuer") != f"{origin}/authentik/application/o/rallly/":
                raise ValueError("L'émetteur OIDC ne correspond pas au tunnel")

            return
        except (OSError, URLError, ValueError) as error:
            last_error = error
            time.sleep(min(1, max(0, deadline - time.monotonic())))

    raise RuntimeError(f"Le tunnel n'est pas prêt : {last_error}")


def show_urls(origin: str, email_login: bool = False):
    print(f"\nRallly       : {origin}/", flush=True)
    print(f"Authentik    : {origin}/authentik/", flush=True)
    print(f"Administration : {origin}/authentik/if/admin/", flush=True)
    print(f"Callback OIDC  : {origin}/api/auth/callback/oidc", flush=True)

    if email_login:
        print("Mailpit (local) : http://localhost:8025", flush=True)
        print("Les codes email sont consultables dans Mailpit sur cet ordinateur.", flush=True)

    print("\nCtrl+C pour arrêter le tunnel et restaurer l'origine précédente.", flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=90, help="Délai de création du tunnel en secondes (90 par défaut)")
    parser.add_argument("--verbose", action="store_true", help="Afficher les journaux ngrok")
    parser.add_argument("--email-login", action="store_true", help="Activer la connexion par email avec Mailpit en local")
    args = parser.parse_args(argv)
    executable = shutil.which("ngrok")
    root = Path(__file__).resolve().parents[1]

    if executable is None:
        parser.error("ngrok est requis : brew install ngrok, puis ngrok config add-authtoken TON_TOKEN")

    if args.timeout <= 0:
        parser.error("--timeout doit être supérieur à zéro")

    if not (root / ".env").is_file():
        parser.error("Créer .env depuis .env.example et renseigner les secrets avant de démarrer")

    tunnel = None
    configuration_started = False
    previous_origin = None
    exit_code = 0

    try:
        local_origin, previous_origin = read_configuration(root)
        subprocess.run(
            ["docker", "compose", "up", "-d", "--wait", "--wait-timeout", "240"],
            cwd=root,
            check=True,
        )
        tunnel = NgrokTunnel(executable, local_origin, args.verbose)
        print(f"Connexion d'un tunnel ngrok partagé vers {local_origin}…", flush=True)
        tunnel.start()
        public_origin = tunnel.wait_url(args.timeout)
        print(f"Tunnel connecté : {public_origin}\nConfiguration de la stack…", flush=True)

        configuration_started = True
        apply_public_url(root, public_origin, email_login=args.email_login)
        print("Vérification de Rallly et d'Authentik via le tunnel…", flush=True)
        wait_ready(tunnel, public_origin, args.timeout)
        show_urls(public_origin, email_login=args.email_login)
        exit_code = tunnel.wait()

        if exit_code != 0:
            raise RuntimeError(f"ngrok s'est arrêté avec le code {exit_code}")
    except KeyboardInterrupt:
        print("\nArrêt du tunnel…", flush=True)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        exit_code = 1

        if tunnel is not None and not args.verbose:
            for line in list(tunnel.logs):
                print(line, file=sys.stderr)
    finally:
        if tunnel is not None:
            tunnel.stop()

        if configuration_started and previous_origin is not None:
            print(f"Restauration de l'origine précédente : {previous_origin}", flush=True)

            try:
                apply_public_url(root, previous_origin)
            except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
                print(f"Restauration échouée : {error}", file=sys.stderr)
                print(f"Relancer : python3 scripts/set-public-url.py {previous_origin}", file=sys.stderr)
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
