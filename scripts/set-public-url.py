"""Update the shared public origin, containers and Authentik OIDC configuration."""

import argparse
from pathlib import Path
import subprocess
from urllib.parse import urlsplit, urlunsplit


def parse_origin(value):
    url = urlsplit(value)

    if url.scheme not in ("http", "https") or not url.hostname:
        raise argparse.ArgumentTypeError("Use an HTTP or HTTPS origin")

    if url.path not in ("", "/") or url.query or url.fragment or url.username or url.password:
        raise argparse.ArgumentTypeError("The origin must not contain a path, credentials, query or fragment")

    if url.hostname in ("localhost", "127.0.0.1", "::1"):
        raise argparse.ArgumentTypeError("For local OIDC, use http://rallly.localhost")

    try:
        port = url.port
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error

    host = url.hostname

    if port and (url.scheme, port) not in (("http", 80), ("https", 443)):
        host = f"{host}:{port}"

    return urlunsplit((url.scheme, host, "", "", ""))


def update_environment(filename, origin):
    lines = filename.read_text().splitlines()
    lines = [line for line in lines if not line.startswith("PUBLIC_BASE_URL=")]
    filename.write_text("\n".join([f"PUBLIC_BASE_URL={origin}", *lines]) + "\n")


def configure_authentik(root, compose):
    source = """
from os import environ

from django.core.management import call_command
from django.db import transaction

from authentik.tenants.utils import get_current_tenant

with transaction.atomic():
    tenant = get_current_tenant()
    tenant.base_url = environ["PUBLIC_BASE_URL"]
    tenant.save(update_fields=["base_url"])
    call_command("apply_blueprint", "custom/rallly.yaml")
"""
    command = [*compose, "exec", "-T", "authentik_worker", "ak", "shell"]
    result = subprocess.run(command, input=source, text=True, capture_output=True, cwd=root)

    if result.returncode != 0:
        raise RuntimeError("Authentik configuration failed; inspect docker compose logs authentik_worker")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin", type=parse_origin, help="https://xxxx.ngrok-free.app or http://rallly.localhost")
    parser.add_argument("--email-login", action="store_true", help="Enable email login with the local Mailpit inbox")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    filename = root / ".env"

    if not filename.is_file():
        parser.error("Create .env from .env.example and fill in its secrets first")

    compose = ["docker", "compose", "-f", "docker-compose.yaml"]

    if args.email_login:
        compose.extend(["-f", "docker-compose.email.yaml"])

    update_environment(filename, args.origin)
    subprocess.run([*compose, "config", "--quiet"], cwd=root, check=True)
    subprocess.run([*compose, "up", "-d", "--wait", "--wait-timeout", "240"], cwd=root, check=True)
    configure_authentik(root, compose)

    print(f"Rallly: {args.origin}/")
    print(f"Authentik: {args.origin}/authentik/")
    print(f"OIDC callback: {args.origin}/api/auth/callback/oidc")

    if args.email_login:
        print("Mailpit (local only): http://localhost:8025")


if __name__ == "__main__":
    main()
