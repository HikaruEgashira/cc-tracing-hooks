"""CLI for otel-hooks."""

import argparse
import sys
from importlib.metadata import version

import questionary
from rich.console import Console

from . import config as cfg
from .tools import Scope, available_tools, get_tool, ToolConfig

console = Console(stderr=True)

PROVIDERS = ["langfuse", "otlp", "datadog"]
TOOLS = available_tools()
TOOL_CHOICES = [*TOOLS, "all"]


class _NoTTYError(SystemExit):
    def __init__(self, flag: str) -> None:
        super().__init__(f"No TTY detected. Use {flag} to run non-interactively.")


def _is_tty() -> bool:
    return sys.stdin.isatty()


def _require_tty(flag: str) -> None:
    if not _is_tty():
        raise _NoTTYError(flag)


def _select(message: str, choices: list[str], flag: str) -> str:
    _require_tty(flag)
    selected = questionary.select(message, choices=choices).ask()
    if selected is None:
        raise SystemExit(1)
    return selected


def _confirm(message: str, *, default: bool = False) -> bool:
    _require_tty("--yes")
    result = questionary.confirm(message, default=default).ask()
    if result is None:
        raise SystemExit(1)
    return result


def _text(message: str, *, default: str = "", flag: str = "") -> str:
    if flag:
        _require_tty(flag)
    result = questionary.text(message, default=default).ask()
    return result or default


def _password(message: str, *, flag: str = "") -> str:
    if flag:
        _require_tty(flag)
    result = questionary.password(message).ask()
    return result or ""


def _resolve_tools(args: argparse.Namespace) -> list[str]:
    """Return list of tool names to operate on."""
    tool = getattr(args, "tool", None)
    if tool == "all":
        return list(TOOLS)
    if tool:
        return [tool]

    selected = _select("Which tool?", TOOL_CHOICES, "--tool")
    return list(TOOLS) if selected == "all" else [selected]


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

    return _select("Which provider?", PROVIDERS, "--provider")


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
    codex_cfg = codex.load_settings(Scope.GLOBAL)

    if provider == "langfuse":
        public_key = _text("LANGFUSE_PUBLIC_KEY:")
        secret_key = _password("LANGFUSE_SECRET_KEY:")
        base_url = _text("LANGFUSE_BASE_URL:", default="https://cloud.langfuse.com")
        codex_cfg = codex.enable_langfuse(codex_cfg, public_key, secret_key, base_url)
    elif provider == "otlp":
        endpoint = _text("OTEL_EXPORTER_OTLP_ENDPOINT:")
        headers = _text("OTEL_EXPORTER_OTLP_HEADERS (k=v,k=v):")
        codex_cfg = codex.enable_otlp(codex_cfg, endpoint, headers)
    else:
        console.print(f"[red]Provider '{provider}' is not supported for codex. Use langfuse or otlp.[/red]")
        return 1

    codex.save_settings(codex_cfg, Scope.GLOBAL)
    console.print(f"[green]Enabled.[/green] Settings written to {codex.settings_path(Scope.GLOBAL)}")
    return 0


def _enable_one(tool_name: str, args: argparse.Namespace) -> int:
    if tool_name == "codex":
        return _enable_codex(args)

    tool_cfg = get_tool(tool_name)
    scope = _resolve_scope(args, tool_cfg)
    provider = _resolve_provider(args)

    with console.status(f"Enabling {tool_name} ({scope.value}, provider={provider})..."):
        tool_settings = tool_cfg.load_settings(scope)
        tool_settings = tool_cfg.register_hook(tool_settings)
        tool_cfg.save_settings(tool_settings, scope)

        config_scope = Scope.PROJECT if scope is Scope.PROJECT else Scope.GLOBAL
        otel_cfg = cfg.load_raw_config(config_scope)
        otel_cfg["provider"] = provider

    provider_keys = cfg.env_keys_for_provider(provider)
    if provider_keys:
        merged = cfg.load_config()
        merged_section = merged.get(provider, {})
        section = otel_cfg.setdefault(provider, {})
        for field, env_var in provider_keys:
            if not section.get(field) and not merged_section.get(field):
                if "SECRET" in env_var and scope is Scope.PROJECT:
                    console.print(f"  [dim]{env_var}: skipped (use --local or --global for secrets)[/dim]")
                    continue
                ask_fn = _password if "SECRET" in env_var else _text
                value = ask_fn(f"{env_var}:")
                if value:
                    section[field] = value

    cfg.save_config(otel_cfg, config_scope)
    console.print(f"[green]Enabled.[/green] Hook: {tool_cfg.settings_path(scope)}, Config: {cfg.config_path(config_scope)}")
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    tools = _resolve_tools(args)
    rc = 0
    for tool_name in tools:
        try:
            rc |= _enable_one(tool_name, args)
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] failed to enable {tool_name}: {e}")
            rc = 1
    return rc


def cmd_disable(args: argparse.Namespace) -> int:
    tools = _resolve_tools(args)
    rc = 0
    for tool_name in tools:
        try:
            tool_cfg = get_tool(tool_name)
            scope = _resolve_scope(args, tool_cfg)

            tool_settings = tool_cfg.load_settings(scope)
            tool_settings = tool_cfg.unregister_hook(tool_settings)
            tool_cfg.save_settings(tool_settings, scope)

            console.print(f"[green]Disabled.[/green] {tool_cfg.settings_path(scope)}")
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] failed to disable {tool_name}: {e}")
            rc = 1

    return rc


def cmd_status(args: argparse.Namespace) -> int:
    from rich.table import Table

    tool = getattr(args, "tool", None)
    tools = list(TOOLS) if not tool or tool == "all" else [tool]

    otel_config = cfg.load_config()
    provider = otel_config.get("provider", "(not set)")

    table = Table(title="otel-hooks status")
    table.add_column("Tool")
    table.add_column("Scope")
    table.add_column("Hook")
    table.add_column("Path")

    for name in tools:
        tool_cfg = get_tool(name)
        for scope in tool_cfg.scopes():
            tool_settings = tool_cfg.load_settings(scope)
            registered = tool_cfg.is_hook_registered(tool_settings)
            path = str(tool_cfg.settings_path(scope))
            status = "[green]registered[/green]" if registered else "[dim]not registered[/dim]"
            table.add_row(name, scope.value, status, path)

    console.print(table)
    console.print(f"Provider: [bold]{provider}[/bold]")

    if provider and provider in ("langfuse", "otlp", "datadog"):
        pcfg = otel_config.get(provider, {})
        for field, env_var in cfg.env_keys_for_provider(provider):
            val = pcfg.get(field, "")
            masked = _mask(val) if "SECRET" in env_var and val else (val or "(not set)")
            console.print(f"  {env_var}: {masked}")

    return 0


def _doctor_one(tool_name: str, args: argparse.Namespace) -> int:
    tool_cfg = get_tool(tool_name)
    scope = tool_cfg.scopes()[0]
    tool_settings = tool_cfg.load_settings(scope)
    issues: list[str] = []

    if not tool_cfg.is_hook_registered(tool_settings):
        issues.append(f"Hook not registered in {tool_cfg.settings_path(scope)}")

    otel_config = cfg.load_config()
    provider = otel_config.get("provider")

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
        console.print(f"[green]{tool_name}: No issues found.[/green]")
        return 0

    console.print(f"[yellow]{tool_name}: Found {len(issues)} issue(s):[/yellow]")
    for issue in issues:
        console.print(f"  [red]- {issue}[/red]")

    yes = getattr(args, "yes", False)
    if not yes and not _confirm("Fix automatically?"):
        return 1

    # Fix hook registration
    if not tool_cfg.is_hook_registered(tool_settings):
        tool_settings = tool_cfg.register_hook(tool_settings)
        tool_cfg.save_settings(tool_settings, scope)

    # Fix otel-hooks config
    config_scope = Scope.PROJECT if getattr(args, "project", False) else Scope.GLOBAL
    otel_cfg = cfg.load_raw_config(config_scope)
    if not provider:
        provider = _resolve_provider(args)
    otel_cfg["provider"] = provider

    for field, env_var in cfg.env_keys_for_provider(provider or ""):
        section = otel_cfg.setdefault(provider, {})
        if not section.get(field):
            ask_fn = _password if "SECRET" in env_var else _text
            value = ask_fn(f"{env_var}:")
            if value:
                section[field] = value

    cfg.save_config(otel_cfg, config_scope)
    console.print("[green]Fixed.[/green]")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    tools = _resolve_tools(args)
    rc = 0
    for tool_name in tools:
        try:
            rc |= _doctor_one(tool_name, args)
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] failed to check {tool_name}: {e}")
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
    p_doctor.add_argument("--yes", "-y", action="store_true",
                          help="Auto-fix without confirmation")

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
        "version": lambda _: console.print(version("otel-hooks")) or 0,
    }
    sys.exit(commands[args.command](args))


if __name__ == "__main__":
    main()
