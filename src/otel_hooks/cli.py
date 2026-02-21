"""CLI for otel-hooks."""

import argparse
import getpass
import os
import sys
from importlib.metadata import version

from . import settings as s
from .settings import Scope


PROVIDERS = ["langfuse", "otlp"]


def _resolve_scope(args: argparse.Namespace) -> Scope:
    if getattr(args, "global_", False):
        return Scope.GLOBAL
    if getattr(args, "project", False):
        return Scope.PROJECT
    if getattr(args, "local", False):
        return Scope.LOCAL

    accessible = os.environ.get("ACCESSIBLE")
    if accessible:
        print("Scope: [g]lobal, [p]roject, or [l]ocal?")
    else:
        print("Where should hooks be configured?")
        print("  [g] global   (~/.claude/settings.json)")
        print("  [p] project  (.claude/settings.json)")
        print("  [l] local    (.claude/settings.local.json)")

    choice = input("Select [g/p/l]: ").strip().lower()
    if choice in ("p", "project"):
        return Scope.PROJECT
    if choice in ("l", "local"):
        return Scope.LOCAL
    return Scope.GLOBAL


def _resolve_provider(args: argparse.Namespace) -> str:
    provider = getattr(args, "provider", None)
    if provider:
        return provider

    print("Which provider?")
    for i, p in enumerate(PROVIDERS, 1):
        print(f"  [{i}] {p}")
    choice = input(f"Select [1-{len(PROVIDERS)}]: ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(PROVIDERS):
            return PROVIDERS[idx]
    except ValueError:
        if choice.lower() in PROVIDERS:
            return choice.lower()
    return "langfuse"


def _add_scope_flags(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--global", dest="global_", action="store_true",
                       help="Write to ~/.claude/settings.json")
    group.add_argument("--project", action="store_true",
                       help="Write to .claude/settings.json (shared with team)")
    group.add_argument("--local", action="store_true",
                       help="Write to .claude/settings.local.json")


def _is_provider_dep_missing(provider: str) -> bool:
    """Check if provider dependencies are installed."""
    try:
        if provider == "langfuse":
            import langfuse  # noqa: F401
        elif provider == "otlp":
            import opentelemetry  # noqa: F401
        return False
    except ImportError:
        return True


def _check_provider_deps(provider: str) -> None:
    """Warn if provider dependencies are not installed."""
    if _is_provider_dep_missing(provider):
        print(f"  WARNING: Dependencies for '{provider}' not found.")
        print(f"  Run: pip install otel-hooks[{provider}]")


def cmd_enable(args: argparse.Namespace) -> int:
    scope = _resolve_scope(args)
    provider = _resolve_provider(args)
    print(f"Enabling tracing hooks ({scope.value}, provider={provider})...")

    # Verify provider dependencies are installed
    _check_provider_deps(provider)

    cfg = s.load_settings(scope)
    cfg = s.register_hook(cfg)
    cfg = s.set_env(cfg, "OTEL_HOOKS_PROVIDER", provider)
    cfg = s.set_env(cfg, "OTEL_HOOKS_ENABLED", "true")

    env_keys = s.env_keys_for_provider(provider)
    for key in env_keys:
        if not s.get_env(cfg, key):
            if "SECRET" in key and scope is Scope.PROJECT:
                print(f"  {key}: skipped (use --local or --global for secrets)")
                continue
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
    cfg = s.set_env(cfg, "OTEL_HOOKS_ENABLED", "false")
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
    provider = s.get_provider(cfg, scope)
    path = s.settings_path(scope)

    print(f"[{scope.value}] {path}")
    print(f"  Status: {'enabled' if enabled else 'disabled'}")
    print(f"  Provider: {provider or '(not set)'}")
    print(f"  Hook registered: {s.is_hook_registered(cfg)}")
    print(f"  Environment:")

    env_status = s.get_env_status(cfg, scope)
    for key, value in env_status.items():
        masked = _mask(value) if "SECRET" in key and value else value
        print(f"    {key}: {masked or '(not set)'}")


def cmd_doctor(args: argparse.Namespace) -> int:
    scope = _resolve_scope(args)
    cfg = s.load_settings(scope)
    provider = s.get_provider(cfg, scope)
    issues: list[str] = []

    if not s.is_hook_registered(cfg):
        issues.append("Hook not registered in settings")

    if not s.is_enabled(cfg, scope):
        issues.append("OTEL_HOOKS_ENABLED is not 'true'")

    if not provider:
        issues.append("OTEL_HOOKS_PROVIDER not set")

    if provider:
        dep_missing = _is_provider_dep_missing(provider)
        if dep_missing:
            issues.append(f"Dependencies for '{provider}' not installed (pip install otel-hooks[{provider}])")

    env = s.get_env_status(cfg, scope)
    if provider == "langfuse":
        if not env.get("LANGFUSE_PUBLIC_KEY"):
            issues.append("LANGFUSE_PUBLIC_KEY not set")
        if not env.get("LANGFUSE_SECRET_KEY"):
            issues.append("LANGFUSE_SECRET_KEY not set")
    elif provider == "otlp":
        if not env.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            issues.append("OTEL_EXPORTER_OTLP_ENDPOINT not set")

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
    if not s.is_enabled(cfg, scope):
        cfg = s.set_env(cfg, "OTEL_HOOKS_ENABLED", "true")

    if not provider:
        provider = _resolve_provider(args)
        cfg = s.set_env(cfg, "OTEL_HOOKS_PROVIDER", provider)

    for key in s.env_keys_for_provider(provider or ""):
        if not env.get(key):
            prompt_fn = getpass.getpass if "SECRET" in key else input
            value = prompt_fn(f"  {key}: ").strip()
            if value:
                cfg = s.set_env(cfg, key, value)
    s.save_settings(cfg, scope)
    print("Fixed.")

    if provider and _is_provider_dep_missing(provider):
        print(f"\n  NOTE: Install provider dependencies: pip install otel-hooks[{provider}]")

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
        description="Claude Code tracing hooks for observability",
    )
    sub = parser.add_subparsers(dest="command")

    p_enable = sub.add_parser("enable", help="Enable tracing hooks")
    _add_scope_flags(p_enable)
    p_enable.add_argument("--provider", choices=PROVIDERS, help="Provider to use")

    p_disable = sub.add_parser("disable", help="Disable tracing hooks")
    _add_scope_flags(p_disable)

    p_status = sub.add_parser("status", help="Show current status")
    _add_scope_flags(p_status)
    p_status.add_argument("--detailed", action="store_true",
                          help="Show detailed status for each scope")

    p_doctor = sub.add_parser("doctor", help="Check and fix configuration issues")
    _add_scope_flags(p_doctor)

    sub.add_parser("hook", help="Run the tracing hook (called by Claude Code)")
    sub.add_parser("version", help="Show version")

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
        "version": lambda _: print(version("otel-hooks")) or 0,
    }
    sys.exit(commands[args.command](args))
