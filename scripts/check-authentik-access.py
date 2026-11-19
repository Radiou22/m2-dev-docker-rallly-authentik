"""Run inside authentik_worker with `ak shell` to verify Rallly access rules."""

from uuid import uuid4

from django.db import transaction

from authentik.blueprints.models import BlueprintInstance
from authentik.blueprints.v1.importer import Importer
from authentik.core.models import Application, Group, User
from authentik.policies.models import PolicyBinding
from authentik.policies.engine import PolicyEngine


def check_access(application, username, groups, expected):
    user = User.objects.create(
        username=username,
        name="Rallly access check",
        email=f"{username}@example.com",
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    user.ak_groups.set(groups)

    engine = PolicyEngine(application, user)
    engine.use_cache = False
    engine.build()

    actual = engine.passing

    if actual != expected:
        raise AssertionError(f"{username}: expected {expected}, got {actual}")

    return user


def check_blueprint_reapply(application, user, group):
    content = BlueprintInstance(path="custom/rallly.yaml").retrieve()
    importer = Importer.from_string(content)
    valid, _ = importer.validate()

    if not valid or not importer.apply():
        raise AssertionError("Blueprint reapplication failed")

    if not group.users.filter(pk=user.pk).exists():
        raise AssertionError("Blueprint reapplication removed a group member")

    bindings = PolicyBinding.objects.filter(target=application, policy__name="rallly-access")

    if bindings.count() != 1:
        raise AssertionError("Blueprint reapplication duplicated the access binding")


def main():
    application = Application.objects.get(slug="rallly")
    allowed = Group.objects.get(name="rallly-allowed")
    denied = Group.objects.get(name="rallly-denied")
    admin = User.objects.get(username="akadmin")
    prefix = f"rallly-check-{uuid4().hex[:12]}"
    cases = [
        ("allowed", [allowed], True),
        ("denied", [denied], False),
        ("both", [allowed, denied], False),
        ("no-group", [], False),
    ]

    if allowed.is_superuser or denied.is_superuser:
        raise AssertionError("Rallly access groups must not grant Authentik administration")

    with transaction.atomic():
        allowed_user = None

        for name, groups, expected in cases:
            user = check_access(application, f"{prefix}-{name}", groups, expected)

            if name == "allowed":
                allowed_user = user

            print(f"PASS {name}: access {'allowed' if expected else 'denied'}")

        admin_groups = list(admin.ak_groups.all())
        check_access(application, f"{prefix}-admin", admin_groups, True)
        check_access(application, f"{prefix}-denied-admin", admin_groups + [denied], False)
        print("PASS admin: access allowed; denied group takes precedence")

        check_blueprint_reapply(application, allowed_user, allowed)
        print("PASS blueprint reapply: membership preserved and access binding unique")

        transaction.set_rollback(True)

    if User.objects.filter(username__startswith=prefix).exists():
        raise AssertionError("Temporary users were not rolled back")

    print("Access checks passed; temporary users rolled back.")


main()
