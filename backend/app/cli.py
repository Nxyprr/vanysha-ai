"""Administración desde la terminal (sin abrir la interfaz).

  python -m app.cli list-users
  python -m app.cli add-user                # pregunta nombre, correo, rol y contraseña
  python -m app.cli set-password --email admin@vanysha.ai
"""
import argparse
import getpass
import os
import sys

from . import config, db, security

ROLES = ("admin", "supervisor", "operador", "auditor")


def create(name, email, role, cargo, password):
    email = email.strip().lower()
    if role not in ROLES:
        raise ValueError("Rol no válido. Usa: " + ", ".join(ROLES))
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    at = email.find("@")
    if at < 1 or email.find(".", at) < at + 2 or " " in email:
        raise ValueError("El correo no es válido.")
    with db.conn() as c:
        if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise ValueError("Ya existe una cuenta con ese correo.")
        u = db.create_user(c, name.strip(), email, cargo or role, role, password)
        db.audit(c, "Terminal", "Cuenta creada: %s (%s)" % (email, role))
    return u


def set_password(email, password):
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    with db.conn() as c:
        n = c.execute("UPDATE users SET pw_hash=? WHERE email=?", (security.hash_password(password), email.strip().lower())).rowcount
        if not n:
            raise ValueError("No existe esa cuenta.")
        db.audit(c, "Terminal", "Contraseña cambiada: " + email)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list-users")
    a = sub.add_parser("add-user")
    for k in ("name", "email", "role", "cargo"):
        a.add_argument("--" + k)
    s = sub.add_parser("set-password")
    s.add_argument("--email")
    s.add_argument("--admin", action="store_true", help="usa la cuenta de la administradora")
    args = ap.parse_args(argv)
    db.init_db()
    try:
        if args.cmd == "list-users":
            with db.conn() as c:
                for r in c.execute("SELECT * FROM users ORDER BY created_at"):
                    print("%-10s %-28s %-11s %s" % (r["id"], r["email"], r["role"], r["name"]))
        elif args.cmd == "add-user":
            name = args.name or input("Nombre completo: ")
            email = args.email or input("Correo: ")
            role = args.role or input("Rol (%s): " % "/".join(ROLES))
            pw = os.getenv("VANYSHA_NEW_PASSWORD") or getpass.getpass("Contraseña (mínimo 8): ")
            u = create(name, email, role, args.cargo, pw)
            print("Cuenta creada:", u["email"], "·", u["role"])
        elif args.cmd == "set-password":
            email = config.ADMIN_EMAIL if args.admin else (args.email or input("Correo: "))
            pw = os.getenv("VANYSHA_NEW_PASSWORD") or getpass.getpass("Nueva contraseña (mínimo 8): ")
            set_password(email, pw)
            print("Contraseña actualizada.")
    except ValueError as e:
        print("Error:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
