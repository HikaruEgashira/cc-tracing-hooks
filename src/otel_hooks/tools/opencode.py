"""OpenCode tool configuration (.opencode/plugins/otel-hooks.js).

Reference:
  - https://opencode.ai/docs/plugins/
"""

import os
from pathlib import Path
from typing import Any, Dict

from . import HookEvent, Scope, _extract_transcript_path, register_tool

PLUGIN_FILE = "otel-hooks.js"
PLUGIN_DIR = Path(".opencode") / "plugins"
PLUGIN_MARKER = "otel-hooks-opencode-plugin-v1"
PLUGIN_SCRIPT = f"""// {PLUGIN_MARKER}
import {{ appendFileSync, mkdirSync }} from "node:fs"
import {{ dirname, join }} from "node:path"
import {{ tmpdir }} from "node:os"
import {{ spawnSync }} from "node:child_process"

const stateRoot = join(tmpdir(), "otel-hooks", "opencode")
const roleByMessageId = new Map()

function ensureParent(filePath) {{
  mkdirSync(dirname(filePath), {{ recursive: true }})
}}

function transcriptPath(sessionID) {{
  return join(stateRoot, `${{sessionID}}.jsonl`)
}}

function appendJsonl(path, obj) {{
  ensureParent(path)
  appendFileSync(path, JSON.stringify(obj) + "\\n", "utf8")
}}

function callHook(payload) {{
  try {{
    spawnSync("otel-hooks", ["hook"], {{
      input: JSON.stringify(payload),
      encoding: "utf8",
    }})
  }} catch (err) {{
    // ignore hook failures from plugin runtime
  }}
}}

function emitTrace(sessionID, path, eventType) {{
  callHook({{
    source_tool: "opencode",
    opencode_event_type: eventType,
    session_id: sessionID,
    transcript_path: path,
  }})
}}

function emitMetric(sessionID, metricName, attributes = {{}}) {{
  callHook({{
    source_tool: "opencode",
    kind: "metric",
    session_id: sessionID,
    metric_name: metricName,
    metric_value: 1,
    metric_attributes: attributes,
  }})
}}

function assistantMessage(messageID, content) {{
  return {{
    type: "assistant",
    message: {{
      id: messageID,
      role: "assistant",
      model: "opencode",
      content,
    }},
  }}
}}

function userMessage(messageID, content) {{
  return {{
    type: "user",
    message: {{
      id: messageID,
      role: "user",
      content,
    }},
  }}
}}

export const OTelHooksPlugin = async () => ({{
  event: async (input) => {{
    const event = input?.event
    if (!event || typeof event !== "object") return

    if (event.type === "message.updated") {{
      const info = event.properties?.info
      if (!info || typeof info !== "object") return
      const sessionID = typeof info.sessionID === "string" ? info.sessionID : ""
      const messageID = typeof info.id === "string" ? info.id : ""
      const role = info.role === "assistant" ? "assistant" : info.role === "user" ? "user" : ""
      if (!sessionID || !messageID || !role) return

      roleByMessageId.set(messageID, role)
      const path = transcriptPath(sessionID)
      if (role === "assistant") {{
        appendJsonl(path, assistantMessage(messageID, []))
      }} else {{
        appendJsonl(path, userMessage(messageID, []))
      }}
      return
    }}

    if (event.type === "message.part.updated") {{
      const part = event.properties?.part
      if (!part || typeof part !== "object") return
      const sessionID = typeof part.sessionID === "string" ? part.sessionID : ""
      const messageID = typeof part.messageID === "string" ? part.messageID : ""
      if (!sessionID || !messageID) return
      const path = transcriptPath(sessionID)
      const role = roleByMessageId.get(messageID)

      if (part.type === "text") {{
        const text = typeof part.text === "string" ? part.text : ""
        if (role === "user") {{
          appendJsonl(path, userMessage(messageID, [{{ type: "text", text }}]))
        }} else {{
          appendJsonl(path, assistantMessage(messageID, [{{ type: "text", text }}]))
        }}
        return
      }}

      if (part.type === "tool") {{
        const toolName = typeof part.tool === "string" && part.tool ? part.tool : "unknown"
        const callID = typeof part.callID === "string" && part.callID ? part.callID : messageID
        const state = part.state && typeof part.state === "object" ? part.state : {{}}
        const inputObj = state.input && typeof state.input === "object" ? state.input : {{}}
        appendJsonl(
          path,
          assistantMessage(messageID, [
            {{ type: "tool_use", id: callID, name: toolName, input: inputObj }},
          ]),
        )

        const status = typeof state.status === "string" ? state.status : ""
        if (status === "running") {{
          emitMetric(sessionID, "tool_started", {{ tool_name: toolName }})
        }}
        if (status === "completed") {{
          const output = typeof state.output === "string" ? state.output : JSON.stringify(state.output ?? "")
          appendJsonl(
            path,
            userMessage(`${{messageID}}:${{callID}}:result`, [
              {{ type: "tool_result", tool_use_id: callID, content: output }},
            ]),
          )
          emitMetric(sessionID, "tool_completed", {{ tool_name: toolName }})
        }}
        if (status === "error") {{
          const err = typeof state.error === "string" ? state.error : "tool_error"
          appendJsonl(
            path,
            userMessage(`${{messageID}}:${{callID}}:result`, [
              {{ type: "tool_result", tool_use_id: callID, content: err }},
            ]),
          )
          emitMetric(sessionID, "tool_failed", {{ tool_name: toolName }})
        }}
      }}
      return
    }}

    if (event.type === "session.idle") {{
      const sessionID =
        event.properties && typeof event.properties.sessionID === "string"
          ? event.properties.sessionID
          : ""
      if (!sessionID) return
      emitTrace(sessionID, transcriptPath(sessionID), event.type)
      emitMetric(sessionID, "session_idle")
    }}
  }},
}})
"""


@register_tool
class OpenCodeConfig:
    @property
    def name(self) -> str:
        return "opencode"

    def scopes(self) -> list[Scope]:
        return [Scope.PROJECT]

    def settings_path(self, scope: Scope) -> Path:
        return Path.cwd() / PLUGIN_DIR / PLUGIN_FILE

    def load_settings(self, scope: Scope) -> Dict[str, Any]:
        path = self.settings_path(scope)
        if not path.exists():
            return {}
        return {"_script": path.read_text(encoding="utf-8")}

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        path = self.settings_path(scope)
        if settings.get("_delete"):
            if path.exists():
                path.unlink()
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        try:
            os.write(fd, settings.get("_script", "").encode("utf-8"))
        finally:
            os.close(fd)
        tmp.replace(path)

    def is_hook_registered(self, settings: Dict[str, Any]) -> bool:
        return PLUGIN_MARKER in settings.get("_script", "")

    def register_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        settings["_script"] = PLUGIN_SCRIPT
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        settings["_delete"] = True
        return settings

    def parse_event(self, payload: Dict[str, Any]) -> HookEvent | None:
        if payload.get("source_tool") != "opencode":
            return None
        if payload.get("kind") == "metric":
            metric_name = payload.get("metric_name")
            if not isinstance(metric_name, str) or not metric_name:
                return None
            raw_attrs = payload.get("metric_attributes")
            attrs: dict[str, str] = {}
            if isinstance(raw_attrs, dict):
                attrs = {str(k): str(v) for k, v in raw_attrs.items() if v is not None}
            session_id = payload.get("session_id")
            sid = session_id if isinstance(session_id, str) else ""
            value = payload.get("metric_value")
            metric_value = float(value) if isinstance(value, (int, float)) else 1.0
            return HookEvent.metric(
                source_tool=self.name,
                session_id=sid,
                metric_name=metric_name,
                metric_value=metric_value,
                metric_attributes=attrs,
            )

        session_id = payload.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            return None
        transcript_path = _extract_transcript_path(payload)
        if transcript_path is None:
            return None
        return HookEvent.trace(
            source_tool=self.name,
            session_id=session_id,
            transcript_path=transcript_path,
        )
