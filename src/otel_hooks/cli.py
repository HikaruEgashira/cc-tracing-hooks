"""CLI for otel-hooks."""

import argparse
import getpass
import sys
from importlib.metadata import version

from . import config as cfg
from .tools import Scope, available_tools, get_tool, ToolConfig


PROVIDERS = ["langfuse", "otlp", "datadog"]
TOOLS = available_tools()
TOOL_CHOICES = [*TOOLS, "all"]


def _resolve_tools(args: argparse.Namespace) -> list[str]:
    """Return list of tool names to operate on."""
    tool = getattr(args, "tool", None)
    if tool == "all":
        return list(TOOLS)
    if tool:
        return [tool]

    print("Which tool?")
    for i, t in enumerate(TOOL_CHOICES, 1):
        print(f"  [{i}] {t}")
    choice = input(f"Select [1-{len(TOOL_CHOICES)}]: ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(TOOL_CHOICES):
            selected = TOOL_CHOICES[idx]
            return list(TOOLS) if selected == "all" else [selected]
    except ValueError:
        if choice.lower() in TOOL_CHOICES:
            selected = choice.lower()
            return list(TOOLS) if selected == "all" else [selected]
    return ["claude"]


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
                       help="Use global scope")
    group.add_argument("--project", action="store_true",
                       help="Use project scope")
    group.add_argument("--local", action="store_true",
                       help="Use local scope")


def _add_tool_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tool", choices=TOOL_CHOICES,
                        help="Target tool (claude, cursor, codex, ... or 'all')")


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
    else:
        print(f"Provider '{provider}' is not supported for codex. Use langfuse or otlp.")
        return 1

    codex.save_settings(cfg, Scope.GLOBAL)
    print(f"Enabled. Settings written to {codex.settings_path(Scope.GLOBAL)}")
    return 0


def _enable_one(tool_name: str, args: argparse.Namespace) -> int:
    if tool_name == "codex":
        return _enable_codex(args)

    tool_cfg = get_tool(tool_name)
    scope = _resolve_scope(args, tool_cfg)
    provider = _resolve_provider(args)
    print(f"Enabling tracing hooks for {tool_name} ({scope.value}, provider={provider})...")

    # Register hook in the tool's own settings
    tool_settings = tool_cfg.load_settings(scope)
    tool_settings = tool_cfg.register_hook(tool_settings)

    tool_cfg.save_settings(tool_settings, scope)
    print(f"  Hook registered: {tool_cfg.settings_path(scope)}")

    # Write provider config to otel-hooks config (shared across all tools)
    config_scope = Scope.PROJECT if scope is Scope.PROJECT else Scope.GLOBAL
    otel_cfg = cfg.load_raw_config(config_scope)
    otel_cfg["provider"] = provider
    otel_cfg["enabled"] = True

    provider_keys = cfg.env_keys_for_provider(provider)
    if provider_keys:
        merged = cfg.load_config()
        merged_section = merged.get(provider, {})
        section = otel_cfg.setdefault(provider, {})
        for field, env_var in provider_keys:
            if not section.get(field) and not merged_section.get(field):
                if "SECRET" in env_var and scope is Scope.PROJECT:
                    print(f"  {env_var}: skipped (use --local or --global for secrets)")
                    continue
                prompt_fn = getpass.getpass if "SECRET" in env_var else input
                value = prompt_fn(f"  {env_var}: ").strip()
                if value:
                    section[field] = value

    cfg.save_config(otel_cfg, config_scope)
    print(f"  Provider config: {cfg.config_path(config_scope)}")
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    tools = _resolve_tools(args)
    rc = 0
    for tool_name in tools:
        try:
            rc |= _enable_one(tool_name, args)
        except Exception as e:
            print(f"Warning: failed to enable {tool_name}: {e}")
            rc = 1
    return rc


def cmd_disable(args: argparse.Namespace) -> int:
    tools = _resolve_tools(args)
    rc = 0
    for tool_name in tools:
        try:
            tool_cfg = get_tool(tool_name)
            scope = _resolve_scope(args, tool_cfg)
            print(f"Disabling tracing hooks for {tool_name} ({scope.value})...")

            tool_settings = tool_cfg.load_settings(scope)
            tool_settings = tool_cfg.unregister_hook(tool_settings)

            tool_cfg.save_settings(tool_settings, scope)
            print(f"Disabled. Settings written to {tool_cfg.settings_path(scope)}")
        except Exception as e:
            print(f"Warning: failed to disable {tool_name}: {e}")
            rc = 1

    # Update otel-hooks config
    if tools:
        config_scope = Scope.PROJECT if getattr(args, "project", False) else Scope.GLOBAL
        otel_cfg = cfg.load_raw_config(config_scope)
        otel_cfg["enabled"] = False
        cfg.save_config(otel_cfg, config_scope)

    return rc


def cmd_status(args: argparse.Namespace) -> int:
    tool = getattr(args, "tool", None)
    tools = list(TOOLS) if not tool or tool == "all" else [tool]

    for i, name in enumerate(tools):
        _print_tool_status(name)
        if i < len(tools) - 1:
            print()
    return 0


def _print_tool_status(tool_name: str) -> None:
    tool_cfg = get_tool(tool_name)
    for scope in tool_cfg.scopes():
        tool_settings = tool_cfg.load_settings(scope)
        hook_registered = tool_cfg.is_hook_registered(tool_settings)
        path = tool_cfg.settings_path(scope)

        print(f"[{tool_name}/{scope.value}] {path}")
        print(f"  Hook registered: {hook_registered}")

    # Show shared otel-hooks config
    otel_config = cfg.load_config()
    provider = otel_config.get("provider", "(not set)")
    enabled = otel_config.get("enabled", False)
    print(f"  Provider: {provider}")
    print(f"  Enabled: {enabled}")
    if provider and provider in ("langfuse", "otlp", "datadog"):
        pcfg = otel_config.get(provider, {})
        for field, env_var in cfg.env_keys_for_provider(provider):
            val = pcfg.get(field, "")
            masked = _mask(val) if "SECRET" in env_var and val else (val or "(not set)")
            print(f"  {env_var}: {masked}")


def _doctor_one(tool_name: str, args: argparse.Namespace) -> int:
    tool_cfg = get_tool(tool_name)
    scope = tool_cfg.scopes()[0]
    tool_settings = tool_cfg.load_settings(scope)
    issues: list[str] = []

    if not tool_cfg.is_hook_registered(tool_settings):
        issues.append(f"Hook not registered in {tool_cfg.settings_path(scope)}")

    otel_config = cfg.load_config()
    provider = otel_config.get("provider")
    enabled = otel_config.get("enabled", False)

    if not enabled:
        issues.append("otel-hooks not enabled (set enabled=true in config)")

    if not provider:
        issues.append("provider not set in otel-hooks config")

    if provider == "langfuse":
        pcfg = otel_config.get("langfuse", {})
        if not pcfg.get("public_key"):
            issues.append("langfuse.public_key not set")
        if not pcfg.get("secret_key"):
            issues.append("langfuse.secret_key not set")
    elif provider == "otlp":
        pcfg = otel_config.get("otlp", {})
        if not pcfg.get("endpoint"):
            issues.append("otlp.endpoint not set")

    if not issues:
        print(f"{tool_name}: No issues found.")
        return 0

    print(f"{tool_name}: Found {len(issues)} issue(s):")
    for issue in issues:
        print(f"  - {issue}")

    answer = input("\nFix automatically? [y/N] ").strip().lower()
    if answer != "y":
        return 1

    # Fix hook registration
    if not tool_cfg.is_hook_registered(tool_settings):
        tool_settings = tool_cfg.register_hook(tool_settings)
        tool_cfg.save_settings(tool_settings, scope)

    # Fix otel-hooks config
    config_scope = Scope.PROJECT if getattr(args, "project", False) else Scope.GLOBAL
    otel_cfg = cfg.load_raw_config(config_scope)
    otel_cfg["enabled"] = True

    if not provider:
        provider = _resolve_provider(args)
    otel_cfg["provider"] = provider

    for field, env_var in cfg.env_keys_for_provider(provider or ""):
        section = otel_cfg.setdefault(provider, {})
        if not section.get(field):
            prompt_fn = getpass.getpass if "SECRET" in env_var else input
            value = prompt_fn(f"  {env_var}: ").strip()
            if value:
                section[field] = value

    cfg.save_config(otel_cfg, config_scope)
    print("Fixed.")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    tools = _resolve_tools(args)
    rc = 0
    for tool_name in tools:
        try:
            rc |= _doctor_one(tool_name, args)
        except Exception as e:
            print(f"Warning: failed to check {tool_name}: {e}")
            rc = 1
    return rc


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


if __name__ == "__main__":
    main()
