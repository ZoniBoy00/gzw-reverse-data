#!/usr/bin/env python3
"""
MCP Server for auto-re-agent (v0.2.0)

Exposes auto-re-agent functionality as MCP tools for use with OpenCode.
Communicates via JSON-RPC 2.0 over stdio.

Usage:
  python re-agent-mcp-server.py

Configuration:
  - Works in the current directory (or RE_AGENT_PROJECT_DIR env var)
  - Uses re-agent.yaml if present, or creates defaults
  - Requires Ghidra + ghidra-ai-bridge for full functionality
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# auto-re-agent imports
# ---------------------------------------------------------------------------
try:
    from re_agent.config import load_config
    from re_agent.config.loader import (
        AgentModelsConfig,
        BackendConfig as REBackendCfg,
        LLMConfig as RELLMCfg,
        OrchestratorConfig,
        OutputConfig,
        ParityConfig,
        ProjectProfile,
        ReAgentConfig,
        ValidationConfig,
    )
    from re_agent.core.models import FunctionTarget, ReversalResult
    from re_agent.core.session import Session
    from re_agent.llm.registry import create_provider
    from re_agent.backend.registry import create_backend
    from re_agent.orchestrator import reverse_single, reverse_class
    from re_agent.parity import run_parity
    from re_agent.parity.source_indexer import SourceIndexer
    from re_agent.parity.engine import read_hooks
    from re_agent.llm.protocol import Message, LLMProvider

    HAS_RE_AGENT = True
except ImportError as exc:
    HAS_RE_AGENT = False
    _IMPORT_ERROR = str(exc)


# ---------------------------------------------------------------------------
# OpenCode CLI Provider — uses your OpenCode GO subscription via CLI
# ---------------------------------------------------------------------------

class OpenCodeCLIProvider:
    """LLM provider that uses `opencode run` CLI to make calls.

    This lets you use your OpenCode GO subscription directly instead of
    needing a separate Anthropic/OpenAI API key for auto-re-agent.
    """

    def __init__(
        self,
        model: str = "opencode-go/deepseek-v4-flash",
        timeout_s: int = 600,
        opencode_bin: str = "opencode",
    ) -> None:
        self._model = model
        self._timeout_s = timeout_s
        self._opencode_bin = opencode_bin
        self.last_cost: float | None = None
        self.last_tokens: dict = {}

    def send(self, messages: list[Message], **kwargs: Any) -> str:
        """Send messages to the LLM and return the text response."""
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        user_messages = [m for m in messages if m.role != "system"]
        prompt = self._render_messages(user_messages)
        return self._run(prompt, system=system or None, model=kwargs.get("model"))

    @property
    def supports_conversations(self) -> bool:
        return False  # Each call is independent via CLI

    def new_conversation(self, system: str) -> str:
        raise NotImplementedError("OpenCodeCLIProvider does not support conversations")

    def resume(self, conversation_id: str, message: str) -> str:
        raise NotImplementedError("OpenCodeCLIProvider does not support conversations")

    def _run(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
    ) -> str:
        cmd = [
            self._opencode_bin,
            "run",
            "--format",
            "json",
            "--model",
            str(model or self._model),
        ]
        # Add system prompt if provided
        if system is not None:
            full_prompt = f"[SYSTEM]\n{system}\n\n[USER]\n{prompt}"
        else:
            full_prompt = prompt
        cmd.append(full_prompt)

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
                check=False,
                encoding="utf-8",
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"opencode CLI timed out after {self._timeout_s}s"
            ) from exc
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"opencode CLI not found: {self._opencode_bin}"
            ) from exc

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            raise RuntimeError(
                f"opencode CLI failed (exit {proc.returncode}):\n"
                f"stderr: {stderr[:500]}\n"
                f"stdout: {stdout[:500]}"
            )

        # Parse JSON lines output — we want the last "text" event
        text_response = ""
        cost = None
        tokens_info = {}

        for line in proc.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")
            if event_type == "text":
                part = event.get("part", {})
                if isinstance(part, dict) and part.get("type") == "text":
                    text_response = part.get("text", "")
            elif event_type == "step_finish":
                part = event.get("part", {})
                if isinstance(part, dict):
                    tokens_info = part.get("tokens", {})
                    cost = part.get("cost")

        self.last_cost = cost
        self.last_tokens = tokens_info

        if not text_response:
            # Fallback: return last non-empty line
            lines = [l for l in proc.stdout.strip().split("\n") if l.strip()]
            if lines:
                text_response = lines[-1]

        return text_response

    @staticmethod
    def _render_messages(messages: list[Message]) -> str:
        """Render messages into a prompt string."""
        parts = []
        for m in messages:
            role_tag = m.role.upper()
            parts.append(f"[{role_tag}]\n{m.content.strip()}")
        return "\n\n".join(parts).strip()

    def __repr__(self) -> str:
        return f"OpenCodeCLIProvider(model={self._model})"


# ---------------------------------------------------------------------------
# MCP Protocol helpers (JSON-RPC 2.0 over stdio)
# ---------------------------------------------------------------------------

def _send(msg: dict) -> None:
    """Write a JSON-RPC message to stdout, framed with Content-Length."""
    payload = json.dumps(msg, default=str)
    # Use binary write for reliability on Windows
    raw = f"Content-Length: {len(payload)}\r\n\r\n{payload}".encode("utf-8")
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def _respond(id: Any, result: Any = None, error: dict | None = None) -> None:
    if error:
        _send({"jsonrpc": "2.0", "id": id, "error": error})
    else:
        _send({"jsonrpc": "2.0", "id": id, "result": result})


def _json_error(code: int, message: str, data: Any = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return err


def _read_message() -> dict | None:
    """Read a single JSON-RPC message from stdin (Content-Length framed)."""
    content_length = 0
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.decode("utf-8", errors="replace").strip()
        if not line:
            break
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())

    if content_length <= 0:
        return None

    body = sys.stdin.buffer.read(content_length).decode("utf-8", errors="replace")
    return json.loads(body) if body.strip() else None


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

class ReAgentMCPServer:
    """MCP server wrapping auto-re-agent's Python API."""

    def __init__(self) -> None:
        self._initialized = False
        self._config: ReAgentConfig | None = None
        self._backend = None
        self._llm = None
        self._checker_llm = None
        self._session: Session | None = None
        self._indexer: SourceIndexer | None = None

        # Resolve project directory
        self._project_dir = Path(
            os.environ.get("RE_AGENT_PROJECT_DIR", os.getcwd())
        ).resolve()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _do_initialize(self) -> dict:
        self._initialized = True
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
            },
            "serverInfo": {
                "name": "auto-re-agent",
                "version": "0.2.0",
            },
        }

    def _load_or_create_config(self) -> ReAgentConfig:
        """Load re-agent.yaml or create a minimal default config."""
        yaml_path = self._project_dir / "re-agent.yaml"
        if yaml_path.exists():
            return load_config(yaml_path)
        # Return minimal defaults — the user can run re-agent init later
        return ReAgentConfig(
            project_profile=ProjectProfile(
                name="generic-cpp",
                source_root="src",
                language_standard="C++20",
                hook_patterns=[],
                stub_patterns=[],
                stub_markers=[],
                stub_call_prefix="",
                class_macro="",
                source_extensions=[".cpp", ".h", ".hpp"],
                hooks_csv=None,
                prompt_rules=[],
            ),
            llm=RELLMCfg(
                provider="opencode-cli",
                model="opencode-go/deepseek-v4-flash",
                cli_path="opencode",
            ),
            backend=REBackendCfg(type="ghidra-bridge", cli_path="ghidra-bridge", timeout_s=60),
            parity=ParityConfig(enabled=False),
            orchestrator=OrchestratorConfig(
                max_review_rounds=3,
                max_functions_per_class=20,
                investigation_enabled=True,
                max_investigations=5,
                selection_strategy="dependency-order",
                max_attempts_per_function=2,
                objective_verifier_enabled=True,
                objective_call_count_tolerance=2,
                objective_control_flow_tolerance=1,
            ),
            output=OutputConfig(
                report_dir="reports/re-agent",
                log_dir="reports/re-agent/logs",
                session_file="re-agent-progress.json",
                format="json",
            ),
            agents=AgentModelsConfig(reverser=None, checker=None),
            validation=ValidationConfig(enabled=False),
        )

    def _ensure_config(self) -> ReAgentConfig:
        if self._config is None:
            self._config = self._load_or_create_config()
        return self._config

    def _ensure_session(self) -> Session:
        if self._session is None:
            cfg = self._ensure_config()
            session_path = self._project_dir / cfg.output.session_file
            self._session = Session(str(session_path))
            self._session.load()
        return self._session

    def _ensure_indexer(self) -> SourceIndexer | None:
        if self._indexer is None:
            cfg = self._ensure_config()
            src = self._project_dir / cfg.project_profile.source_root
            if src.is_dir():
                self._indexer = SourceIndexer(src, cfg.project_profile)
        return self._indexer

    def _try_init_backend(self) -> tuple[Any, str | None]:
        """Initialize backend. Returns (backend, error_message)."""
        if self._backend is not None:
            return self._backend, None
        try:
            cfg = self._ensure_config()
            self._backend = create_backend(cfg.backend)
            return self._backend, None
        except Exception as exc:
            return None, f"Backend init failed: {exc}"

    def _create_llm_from_config(self, llm_cfg) -> Any:
        """Create LLM provider from config, supporting opencode-cli."""
        if llm_cfg.provider == "opencode-cli":
            return OpenCodeCLIProvider(
                model=llm_cfg.model or "opencode-go/deepseek-v4-flash",
                timeout_s=llm_cfg.timeout_s or 600,
                opencode_bin=llm_cfg.cli_path or "opencode",
            )
        return create_provider(llm_cfg)

    def _try_init_llm(self) -> tuple[Any, str | None]:
        """Initialize primary LLM. Returns (provider, error_message)."""
        if self._llm is not None:
            return self._llm, None
        try:
            cfg = self._ensure_config()
            self._llm = self._create_llm_from_config(cfg.llm)
            return self._llm, None
        except Exception as exc:
            return None, f"LLM init failed: {exc}"

    def _try_init_checker_llm(self) -> tuple[Any, str | None]:
        """Initialize checker LLM (falls back to primary)."""
        if self._checker_llm is not None:
            return self._checker_llm, None
        try:
            cfg = self._ensure_config()
            if cfg.agents and cfg.agents.checker:
                self._checker_llm = self._create_llm_from_config(cfg.agents.checker)
            else:
                self._checker_llm, err = self._try_init_llm()
                return self._checker_llm, err
            return self._checker_llm, None
        except Exception as exc:
            return None, f"Checker LLM init failed: {exc}"

    # ------------------------------------------------------------------
    # Tool: reverse-single
    # ------------------------------------------------------------------

    def _tool_reverse_single(self, args: dict) -> dict:
        address = args.get("address", "")
        class_name = args.get("class_name", "")
        function_name = args.get("function_name", "")
        
        if not address:
            return {"error": "Missing required argument: address"}

        target = FunctionTarget(
            address=address,
            class_name=class_name or "",
            function_name=function_name or "",
        )

        config = self._ensure_config()
        session = self._ensure_session()
        indexer = self._ensure_indexer()

        backend, err = self._try_init_backend()
        if err:
            return {"error": err}

        llm, err = self._try_init_llm()
        if err:
            return {"error": err}

        checker_llm, err = self._try_init_checker_llm()
        if err:
            return {"error": err}

        try:
            result = reverse_single(
                target=target,
                config=config,
                backend=backend,
                llm=llm,
                session=session,
                output_dir=self._project_dir / config.output.report_dir,
                indexer=indexer,
                checker_llm=checker_llm,
            )
            return _result_to_dict(result)
        except Exception as exc:
            return {"error": str(exc), "traceback": traceback.format_exc()}

    # ------------------------------------------------------------------
    # Tool: reverse-class
    # ------------------------------------------------------------------

    def _tool_reverse_class(self, args: dict) -> dict:
        class_name = args.get("class_name", "")
        max_functions = args.get("max_functions", 10)

        if not class_name:
            return {"error": "Missing required argument: class_name"}

        config = self._ensure_config()
        backend, err = self._try_init_backend()
        if err:
            return {"error": err}

        llm, err = self._try_init_llm()
        if err:
            return {"error": err}

        checker_llm, err = self._try_init_checker_llm()
        if err:
            return {"error": err}

        session = self._ensure_session()

        try:
            results = reverse_class(
                class_name=class_name,
                config=config,
                backend=backend,
                llm=llm,
                session=session,
                max_functions=max_functions,
                checker_llm=checker_llm,
            )
            return {"results": [_result_to_dict(r) for r in results], "count": len(results)}
        except Exception as exc:
            return {"error": str(exc), "traceback": traceback.format_exc()}

    # ------------------------------------------------------------------
    # Tool: decompile (just Ghidra decompilation, no LLM)
    # ------------------------------------------------------------------

    def _tool_decompile(self, args: dict) -> dict:
        address = args.get("address", "")
        if not address:
            return {"error": "Missing required argument: address"}

        backend, err = self._try_init_backend()
        if err:
            return {"error": err}

        try:
            decomp = backend.decompile(address)
            asm = backend.get_asm(address)
            xrefs_to = backend.xrefs_to(address)
            xrefs_from = backend.xrefs_from(address)

            result: dict[str, Any] = {
                "address": address,
                "decompile": decomp,
                "assembly": asm,
            }

            # Try optional evidence
            try:
                result["context"] = backend.get_context(address)
            except Exception:
                pass
            try:
                result["pcode"] = backend.get_pcode(address)
            except Exception:
                pass
            try:
                result["cfg"] = backend.get_cfg(address)
            except Exception:
                pass

            return result
        except Exception as exc:
            return {"error": str(exc), "traceback": traceback.format_exc()}

    # ------------------------------------------------------------------
    # Tool: status
    # ------------------------------------------------------------------

    def _tool_status(self, args: dict) -> dict:
        class_filter = args.get("class_name", "")
        session = self._ensure_session()

        try:
            if class_filter:
                summary = session.get_class_summary(class_filter)
            else:
                summary = session.get_summary()

            functions = session.get_all_functions()
            return {
                "summary": summary,
                "functions": functions,
            }
        except Exception as exc:
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Tool: parity
    # ------------------------------------------------------------------

    def _tool_parity(self, args: dict) -> dict:
        config = self._ensure_config()
        backend, _ = self._try_init_backend()

        try:
            # Try to read hooks CSV if configured
            hooks_csv = config.project_profile.hooks_csv
            if hooks_csv:
                hooks_path = self._project_dir / hooks_csv
                if hooks_path.exists():
                    hooks = read_hooks(str(hooks_path))
                else:
                    hooks = []
            else:
                hooks = []

            source_root = self._project_dir / config.project_profile.source_root
            if not source_root.is_dir():
                return {"error": f"Source root not found: {source_root}"}

            results = run_parity(
                hooks=hooks,
                source_root=source_root,
                config=config,
                backend=backend,
            )
            return {"results": results, "count": len(results)}
        except Exception as exc:
            return {"error": str(exc), "traceback": traceback.format_exc()}

    # ------------------------------------------------------------------
    # Tool: estimate
    # ------------------------------------------------------------------

    def _tool_estimate(self, args: dict) -> dict:
        address = args.get("address", "")
        class_name = args.get("class_name", "")

        if not address and not class_name:
            return {"error": "Provide either address or class_name"}

        backend, err = self._try_init_backend()
        if err:
            return {"error": err}

        try:
            estimates = []
            if address:
                decomp = backend.decompile(address)
                asm = backend.get_asm(address)
                estimates.append({
                    "address": address,
                    "decompile_len": len(decomp or ""),
                    "asm_len": len(asm or ""),
                    "estimated_tokens": len(decomp or "") // 4 + len(asm or "") // 2,
                })
            if class_name:
                # Estimate for all functions in class
                remaining = backend.remaining() if hasattr(backend, 'remaining') else []
                # Filter by class if possible
                estimates.append({
                    "class_name": class_name,
                    "note": "Run reverse --dry-run for full estimate",
                })
            return {"estimates": estimates}
        except Exception as exc:
            return {"error": str(exc), "traceback": traceback.format_exc()}

    # ------------------------------------------------------------------
    # Tool: config-info
    # ------------------------------------------------------------------

    def _tool_config_info(self, args: dict) -> dict:
        config = self._ensure_config()
        try:
            return {
                "project": config.project_profile.name,
                "source_root": config.project_profile.source_root,
                "language": config.project_profile.language_standard,
                "llm_provider": config.llm.provider,
                "llm_model": config.llm.model,
                "backend_type": config.backend.type,
                "backend_cli": config.backend.cli_path,
                "config_path": str(self._project_dir / "re-agent.yaml"),
            }
        except Exception as exc:
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Tool: init-config
    # ------------------------------------------------------------------

    def _tool_init_config(self, args: dict) -> dict:
        profile = args.get("profile", "generic-cpp")
        yaml_path = self._project_dir / "re-agent.yaml"

        if yaml_path.exists():
            return {"error": f"Config already exists: {yaml_path}", "path": str(yaml_path)}

        import subprocess
        try:
            result = subprocess.run(
                [sys.executable, "-m", "re_agent.cli.main", "init", "--profile", profile],
                capture_output=True, text=True, timeout=30,
                cwd=str(self._project_dir),
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "path": str(yaml_path) if yaml_path.exists() else None,
            }
        except Exception as exc:
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Tool router
    # ------------------------------------------------------------------

    TOOLS: dict[str, dict] = {
        "reverse-single": {
            "name": "reverse-single",
            "description": "Reverse a single function at a given address using Ghidra + LLM",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Hex address of the function (e.g. 0x401000)"},
                    "class_name": {"type": "string", "description": "Optional class name for context"},
                    "function_name": {"type": "string", "description": "Optional function name"},
                },
                "required": ["address"],
            },
        },
        "reverse-class": {
            "name": "reverse-class",
            "description": "Reverse a batch of functions belonging to a class",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "class_name": {"type": "string", "description": "Class name to reverse"},
                    "max_functions": {"type": "integer", "description": "Max functions to reverse (default 10)"},
                },
                "required": ["class_name"],
            },
        },
        "decompile": {
            "name": "decompile",
            "description": "Decompile a function with Ghidra (no LLM, just decompiler output)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Hex address of the function"},
                },
                "required": ["address"],
            },
        },
        "status": {
            "name": "status",
            "description": "Show reverse engineering session progress",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "class_name": {"type": "string", "description": "Optional class name filter"},
                },
            },
        },
        "parity": {
            "name": "parity",
            "description": "Run parity checks on source vs binary",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "filter": {"type": "string", "description": "Optional regex filter"},
                },
            },
        },
        "estimate": {
            "name": "estimate",
            "description": "Estimate token usage for reversing a function or class",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Hex address of a function"},
                    "class_name": {"type": "string", "description": "Class name"},
                },
            },
        },
        "config-info": {
            "name": "config-info",
            "description": "Show current auto-re-agent configuration",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        "init-config": {
            "name": "init-config",
            "description": "Initialize a re-agent.yaml config file from a profile",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "profile": {
                        "type": "string",
                        "description": "Profile name: generic-cpp, windows-x64, gta-reversed, openrct2",
                    },
                },
            },
        },
    }

    def _handle_tools_list(self, id: Any) -> None:
        _respond(id, {"tools": list(self.TOOLS.values())})

    def _handle_tools_call(self, id: Any, params: dict) -> None:
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        handlers = {
            "reverse-single": self._tool_reverse_single,
            "reverse-class": self._tool_reverse_class,
            "decompile": self._tool_decompile,
            "status": self._tool_status,
            "parity": self._tool_parity,
            "estimate": self._tool_estimate,
            "config-info": self._tool_config_info,
            "init-config": self._tool_init_config,
        }

        handler = handlers.get(name)
        if not handler:
            _respond(id, error=_json_error(-32601, f"Tool not found: {name}"))
            return

        try:
            result = handler(arguments)
            _respond(id, result)
        except Exception as exc:
            _respond(id, error=_json_error(-32603, str(exc), traceback.format_exc()))

    # ------------------------------------------------------------------
    # Message dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, msg: dict) -> None:
        msg_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params", {})

        if method == "initialize":
            _respond(msg_id, self._do_initialize())
            return

        if method == "notifications/initialized":
            return  # no response needed

        if method == "ping":
            _respond(msg_id, {})
            return

        if method == "tools/list":
            self._handle_tools_list(msg_id)
            return

        if method == "tools/call":
            self._handle_tools_call(msg_id, params)
            return

        # Method not found
        _respond(msg_id, error=_json_error(-32601, f"Method not found: {method}"))

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        while True:
            msg = _read_message()
            if msg is None:
                break
            try:
                self._dispatch(msg)
            except Exception as exc:
                msg_id = msg.get("id")
                if msg_id is not None:
                    _respond(msg_id, error=_json_error(-32603, str(exc), traceback.format_exc()))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result_to_dict(result: ReversalResult) -> dict:
    """Convert a ReversalResult to a JSON-safe dict."""
    return {
        "address": result.target.address if result.target else "",
        "class_name": result.target.class_name if result.target else "",
        "function_name": result.target.function_name if result.target else "",
        "success": result.success,
        "rounds_used": result.rounds_used,
        "code": result.code,
        "checker_verdict": str(result.checker_verdict) if result.checker_verdict else None,
        "objective_verdict": str(result.objective_verdict) if result.objective_verdict else None,
        "validation_verdict": str(result.validation_verdict) if result.validation_verdict else None,
        "parity_status": str(result.parity_status) if result.parity_status else None,
        "parity_findings": result.parity_findings or [],
    }

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if not HAS_RE_AGENT:
        _send({
            "jsonrpc": "2.0",
            "error": {
                "code": -32000,
                "message": f"auto-re-agent not installed: {_IMPORT_ERROR}",
            },
        })
        sys.exit(1)

    server = ReAgentMCPServer()
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        _send({
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": str(exc),
                "data": traceback.format_exc(),
            },
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
