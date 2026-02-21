"""CLI for otel-hooks."""

import argparse
import getpass
import os
import sys

from . import settings as s
from .settings import Scope


def _resolve_scope(args: argparse.Namespace) -> Scope:
    if getattr(args, "global_", False):
        return Scope.GLOBAL
    if getattr(args, "local", False):
        return Scope.LOCAL

    accessible = os.environ.get("ACCESSIBLE")
    if accessible:
        print("Scope: [g]lobal (~/.claude/settings.json) or [l]ocal (.claude/settings.local.json)?")
    else:
        print("Where should hooks be configured?")
        print("  [g] global  (~/.claude/settings.json)")
        print("  [l] local   (.claude/settings.local.json)")

    choice = input("Select [g/l]: ").strip().lower()
    if choice in ("l", "local"):
        return Scope.LOCAL
    return Scope.GLOBAL


def _add_scope_flags(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--global", dest="global_", action="store_true",
                       help="Write to ~/.claude/settings.json")
    group.add_argument("--local", action="store_true",
                       help="Write to .claude/settings.local.json")


def cmd_enable(args: argparse.Namespace) -> int:
    scope = _resolve_scope(args)
    print(f"Enabling tracing hooks ({scope.value})...")

    cfg = s.load_settings(scope)
    cfg = s.register_hook(cfg)

    if s.get_env(cfg, "TRACE_TO_LANGFUSE") != "true":
        cfg = s.set_env(cfg, "TRACE_TO_LANGFUSE", "true")

    for key in ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"]:
        if not s.get_env(cfg, key):
            prompt_fn = getpass.getpass if "SECRET" in key else input
            value = prompt_fn(f"  {key}: ").strip()
            if value:
                cfg = s.set_env(cfg, key, value)

    s.save_settings(cfg, scope)
    print(f"Enabled. Settings written to {s.settings_path(scope)}")
    return 0


def cmd_disable(args: argparse.Namespace) -> int:
    scope = _resolve_scope(args)
    print(f"Disabling tracing hooks ({scope.value})...")

    cfg = s.load_settings(scope)
    cfg = s.unregister_hook(cfg)
    cfg = s.set_env(cfg, "TRACE_TO_LANGFUSE", "false")
    s.save_settings(cfg, scope)

    print(f"Disabled. Settings written to {s.settings_path(scope)}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    detailed = getattr(args, "detailed", False)

    if detailed or not (getattr(args, "global_", False) or getattr(args, "local", False)):
        for scope in Scope:
            _print_scope_status(scope)
            print()
    else:
        scope = Scope.GLOBAL if getattr(args, "global_", False) else Scope.LOCAL
        _print_scope_status(scope)
    return 0


def _print_scope_status(scope: Scope) -> None:
    cfg = s.load_settings(scope)
    enabled = s.is_enabled(cfg, scope)
    path = s.settings_path(scope)

    print(f"[{scope.value}] {path}")
    print(f"  Status: {'enabled' if enabled else 'disabled'}")
    print(f"  Hook registered: {s.is_hook_registered(cfg)}")
    print(f"  Environment:")
    for key, value in s.get_env_status(cfg, scope).items():
        masked = _mask(value) if "SECRET" in key and value else value
        print(f"    {key}: {masked or '(not set)'}")


def cmd_doctor(args: argparse.Namespace) -> int:
    scope = _resolve_scope(args)
    cfg = s.load_settings(scope)
    issues: list[str] = []

    if not s.is_hook_registered(cfg):
        issues.append("Hook not registered in settings")

    env = s.get_env_status(cfg, scope)
    if env.get("TRACE_TO_LANGFUSE") != "true":
        issues.append("TRACE_TO_LANGFUSE is not 'true'")
    if not env.get("LANGFUSE_PUBLIC_KEY"):
        issues.append("LANGFUSE_PUBLIC_KEY not set")
    if not env.get("LANGFUSE_SECRET_KEY"):
        issues.append("LANGFUSE_SECRET_KEY not set")

    if not issues:
        print("No issues found.")
        return 0

    print(f"Found {len(issues)} issue(s):")
    for issue in issues:
        print(f"  - {issue}")

    answer = input("\nFix automatically? [y/N] ").strip().lower()
    if answer != "y":
        return 1

    cfg = s.register_hook(cfg)
    if env.get("TRACE_TO_LANGFUSE") != "true":
        cfg = s.set_env(cfg, "TRACE_TO_LANGFUSE", "true")
    for key in ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]:
        if not env.get(key):
            prompt_fn = getpass.getpass if "SECRET" in key else input
            value = prompt_fn(f"  {key}: ").strip()
            if value:
                cfg = s.set_env(cfg, key, value)
    s.save_settings(cfg, scope)
    print("Fixed.")
    return 0


def cmd_hook(_args: argparse.Namespace) -> int:
    from .hook import main as hook_main
    return hook_main()


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-4:]


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="otel-hooks",
        description="Claude Code tracing hooks for Langfuse observability",
    )
    sub = parser.add_subparsers(dest="command")

    p_enable = sub.add_parser("enable", help="Enable tracing hooks")
    _add_scope_flags(p_enable)

    p_disable = sub.add_parser("disable", help="Disable tracing hooks")
    _add_scope_flags(p_disable)

    p_status = sub.add_parser("status", help="Show current status")
    _add_scope_flags(p_status)
    p_status.add_argument("--detailed", action="store_true",
                          help="Show detailed status for each scope")

    p_doctor = sub.add_parser("doctor", help="Check and fix configuration issues")
    _add_scope_flags(p_doctor)

    sub.add_parser("hook", help="Run the tracing hook (called by Claude Code)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "enable": cmd_enable,
        "disable": cmd_disable,
        "status": cmd_status,
        "doctor": cmd_doctor,
        "hook": cmd_hook,
    }
    sys.exit(commands[args.command](args))
