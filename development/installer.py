#!/usr/bin/env python3
import argparse
import os
import subprocess
from pathlib import Path


def cprint(*args, level: int = 1):
    colors = {1: "\033[31m", 2: "\033[92m", 3: "\033[93m"}
    reset = "\033[0m"
    message = " ".join(map(str, args))
    print(f"{colors.get(level, colors[1])} {message} {reset}")


def main():
    parser = get_args_parser()
    args = parser.parse_args()
    bench_path = Path.cwd() / args.bench_name
    init_bench_if_not_exist(args, bench_path)
    create_site_in_bench(args, bench_path)


def get_args_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-j", "--apps-json", type=str, default="apps-example.json", help="Path to apps.json")
    parser.add_argument("-b", "--bench-name", type=str, default="frappe-bench", help="Bench directory name")
    parser.add_argument("-s", "--site-name", type=str, default="development.localhost", help="Site name")
    parser.add_argument("-r", "--frappe-repo", type=str, default="https://github.com/frappe/frappe", help="Frappe repo")
    parser.add_argument("-t", "--frappe-branch", type=str, default="version-16", help="Frappe branch")
    parser.add_argument("-p", "--py-version", type=str, default=None, help="Python version")
    parser.add_argument("-n", "--node-version", type=str, default=None, help="Node version")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-a", "--admin-password", type=str, default="admin", help="Admin password")
    parser.add_argument("-d", "--db-type", type=str, default="mariadb", choices=["mariadb", "postgres"], help="Database type")
    return parser


def init_bench_if_not_exist(args, bench_path: Path):
    if bench_path.exists():
        cprint("Bench already exists. Only site will be created", level=3)
        return

    try:
        env = os.environ.copy()
        if args.py_version:
            env["PYENV_VERSION"] = args.py_version

        init_command = ""
        if args.node_version:
            init_command += f"nvm use {args.node_version}; "
        if args.py_version:
            init_command += f"PYENV_VERSION={args.py_version} "

        init_command += (
            f"bench init --skip-redis-config-generation "
            f"{'--verbose ' if args.verbose else ''}"
            f"--frappe-path={args.frappe_repo} "
            f"--frappe-branch={args.frappe_branch} "
            f"--apps_path={args.apps_json} "
            f"{args.bench_name}"
        )

        subprocess.run(["/bin/bash", "-i", "-c", init_command], env=env, cwd=Path.cwd(), check=True)

        cprint("Configuring Bench ...", level=2)
        configs = [
            ("-g", "db_type", args.db_type),
            ("-g", "redis_cache", "redis://redis-cache:6379"),
            ("-g", "redis_queue", "redis://redis-queue:6379"),
            ("-g", "redis_socketio", "redis://redis-queue:6379"),
            ("-gp", "developer_mode", "1"),
        ]
        for flag, key, val in configs:
            cprint(f"Setting {key} to {val}", level=3)
            subprocess.run(["bench", "set-config", flag, key, val], cwd=bench_path, check=True)

    except subprocess.CalledProcessError as e:
        cprint(f"Command failed with exit code {e.returncode}", level=1)
        raise SystemExit(e.returncode)


def create_site_in_bench(args, bench_path: Path):
    is_mariadb = args.db_type == "mariadb"
    db_host = "mariadb" if is_mariadb else "postgresql"
    db_root_user = "root" if is_mariadb else "postgres"

    cprint(f"Setting db_host to {db_host}", level=3)
    subprocess.run(["bench", "set-config", "-g", "db_host", db_host], cwd=bench_path, check=True)

    new_site_cmd = [
        "bench",
        "new-site",
        f"--db-root-username={db_root_user}",
        f"--db-host={db_host}",
        f"--db-type={args.db_type}",
        "--db-root-password=123",
        f"--admin-password={args.admin_password}",
    ]
    if is_mariadb:
        new_site_cmd.append("--mariadb-user-host-login-scope=%")

    apps_dir = bench_path / "apps"
    if apps_dir.exists():
        apps = [
            d.name for d in apps_dir.iterdir()
            if d.is_dir() and d.name != "frappe" and not d.name.startswith(".")
        ]
        for app in apps:
            new_site_cmd.append(f"--install-app={app}")

    new_site_cmd.append(args.site_name)
    cprint(f"Creating Site {args.site_name} ...", level=2)
    subprocess.run(new_site_cmd, cwd=bench_path, check=True)


if __name__ == "__main__":
    main()
