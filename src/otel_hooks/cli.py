"""CLI for otel-hooks."""

import argparse
import getpass
import os
import sys
from importlib.metadata import version

from . import settings as s
from .settings import Scope
from .tools import available_tools, get_tool, ToolConfig


PROVIDERS = ["langfuse", "otlp"]
TOOLS = ["claude", "cursor", "codex", "opencode", "copilot", "gemini", "kiro", "cline"]


def _resolve_tool(args: argparse.Namespace) -> str:
    tool = getattr(args, "tool", None)
    if tool:
        return tool

    print("Which tool?")
    for i, t in enumerate(TOOLS, 1):
        print(f"  [{i}] {t}")
    choice = input(f"Select [1-{len(TOOLS)}]: ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(TOOLS):
            return TOOLS[idx]
    except ValueError:
        if choice.lower() in TOOLS:
            return choice.lower()
    return "claude"


def _resolve_scope(args: argparse.Namespace, tool_cfg: ToolConfig | None = None) -> Scope:
    if getattr(args, "global_", False):
        return Scope.GLOBAL
    if getattr(args, "project", False):
        return Scope.PROJECT
    if getattr(args, "local", False):
        return Scope.LOCAL

    if tool_cfg:
        scopes = tool_cfg.scopes()
        if Scope.GLOBAL in scopes:
            return Scope.GLOBAL
        return scopes[0]

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


def _add_tool_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tool", choices=TOOLS, help="Target tool (claude, cursor, codex)")


def _enable_codex(args: argparse.Namespace) -> int:
    """Enable tracing for Codex (native OTLP via config.toml)."""
    from .tools.codex import CodexConfig

    provider = _resolve_provider(args)
    codex = CodexConfig()
    cfg = codex.load_settings(Scope.GLOBAL)

    if provider == "langfuse":
        public_key = input("  LANGFUSE_PUBLIC_KEY: ").strip()
        secret_key = getpass.getpass("  LANGFUSE_SECRET_KEY: ").strip()
        base_url = input("  LANGFUSE_BASE_URL [https://cloud.langfuse.com]: ").strip()
        if not base_url:
            base_url = "https://cloud.langfuse.com"
        cfg = codex.enable_langfuse(cfg, public_key, secret_key, base_url)
    elif provider == "otlp":
        endpoint = input("  OTEL_EXPORTER_OTLP_ENDPOINT: ").strip()
        headers = input("  OTEL_EXPORTER_OTLP_HEADERS (k=v,k=v): ").strip()
        cfg = codex.enable_otlp(cfg, endpoint, headers)

    codex.save_settings(cfg, Scope.GLOBAL)
    print(f"Enabled. Settings written to {codex.settings_path(Scope.GLOBAL)}")
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    tool_name = _resolve_tool(args)

    if tool_name == "codex":
        return _enable_codex(args)

    tool_cfg = get_tool(tool_name)
    scope = _resolve_scope(args, tool_cfg)
    provider = _resolve_provider(args)
    print(f"Enabling tracing hooks for {tool_name} ({scope.value}, provider={provider})...")

    cfg = tool_cfg.load_settings(scope)
    cfg = tool_cfg.register_hook(cfg)

    # For Claude, also set env vars in settings
    if tool_name == "claude":
        cfg = tool_cfg.set_env(cfg, "OTEL_HOOKS_PROVIDER", provider)
        cfg = tool_cfg.set_env(cfg, "OTEL_HOOKS_ENABLED", "true")

        env_keys = s.env_keys_for_provider(provider)
        for key in env_keys:
            if not tool_cfg.get_env(cfg, key):
                if "SECRET" in key and scope is Scope.PROJECT:
                    print(f"  {key}: skipped (use --local or --global for secrets)")
                    continue
                prompt_fn = getpass.getpass if "SECRET" in key else input
                value = prompt_fn(f"  {key}: ").strip()
                if value:
                    cfg = tool_cfg.set_env(cfg, key, value)

    tool_cfg.save_settings(cfg, scope)
    print(f"Enabled. Settings written to {tool_cfg.settings_path(scope)}")
    return 0


def cmd_disable(args: argparse.Namespace) -> int:
    tool_name = _resolve_tool(args)
    tool_cfg = get_tool(tool_name)
    scope = _resolve_scope(args, tool_cfg)
    print(f"Disabling tracing hooks for {tool_name} ({scope.value})...")

    cfg = tool_cfg.load_settings(scope)
    cfg = tool_cfg.unregister_hook(cfg)

    if tool_name == "claude":
        cfg = tool_cfg.set_env(cfg, "OTEL_HOOKS_ENABLED", "false")

    tool_cfg.save_settings(cfg, scope)
    print(f"Disabled. Settings written to {tool_cfg.settings_path(scope)}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    tool_name = getattr(args, "tool", None)

    if tool_name:
        _print_tool_status(tool_name)
        return 0

    # Show all tools
    for name in available_tools():
        _print_tool_status(name)
        print()
    return 0


def _print_tool_status(tool_name: str) -> None:
    tool_cfg = get_tool(tool_name)
    for scope in tool_cfg.scopes():
        cfg = tool_cfg.load_settings(scope)
        enabled = tool_cfg.is_enabled(cfg)
        hook_registered = tool_cfg.is_hook_registered(cfg)
        path = tool_cfg.settings_path(scope)

        print(f"[{tool_name}/{scope.value}] {path}")
        print(f"  Status: {'enabled' if enabled else 'disabled'}")
        print(f"  Hook registered: {hook_registered}")

        if tool_name == "claude":
            provider = s.get_provider(cfg, scope)
            print(f"  Provider: {provider or '(not set)'}")
            env_status = s.get_env_status(cfg, scope)
            print(f"  Environment:")
            for key, value in env_status.items():
                masked = _mask(value) if "SECRET" in key and value else value
                print(f"    {key}: {masked or '(not set)'}")


def cmd_doctor(args: argparse.Namespace) -> int:
    tool_name = _resolve_tool(args)

    if tool_name != "claude":
        tool_cfg = get_tool(tool_name)
        scope = tool_cfg.scopes()[0]
        cfg = tool_cfg.load_settings(scope)
        if tool_cfg.is_enabled(cfg):
            print(f"{tool_name}: No issues found.")
        else:
            print(f"{tool_name}: Not configured. Run: otel-hooks enable --tool {tool_name}")
        return 0

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
        description="AI coding tools tracing hooks for observability",
    )
    sub = parser.add_subparsers(dest="command")

    p_enable = sub.add_parser("enable", help="Enable tracing hooks")
    _add_scope_flags(p_enable)
    _add_tool_flag(p_enable)
    p_enable.add_argument("--provider", choices=PROVIDERS, help="Provider to use")

    p_disable = sub.add_parser("disable", help="Disable tracing hooks")
    _add_scope_flags(p_disable)
    _add_tool_flag(p_disable)

    p_status = sub.add_parser("status", help="Show current status")
    _add_scope_flags(p_status)
    _add_tool_flag(p_status)
    p_status.add_argument("--detailed", action="store_true",
                          help="Show detailed status for each scope")

    p_doctor = sub.add_parser("doctor", help="Check and fix configuration issues")
    _add_scope_flags(p_doctor)
    _add_tool_flag(p_doctor)

    p_hook = sub.add_parser("hook", help="Run the tracing hook (called by AI tools)")
    _add_tool_flag(p_hook)

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
