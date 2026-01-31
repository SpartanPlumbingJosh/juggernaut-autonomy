import argparse
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

LOGGER_NAME: str = "juggernaut.update"
DEFAULT_LOG_LEVEL: str = "INFO"
BACKUP_SUFFIX: str = ".bak"
ENCODING: str = "utf-8"


@dataclass(frozen=True)
class UpdatePaths:
    """Holds repository file paths used by the update module."""

    repo_root: Path
    chat_page: Path
    message_bubble: Path


def configure_logging(level: str) -> None:
    """Configures module logging.

    Args:
        level: Logging level name (e.g., 'INFO', 'DEBUG').
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def resolve_paths(repo_root: Path) -> UpdatePaths:
    """Resolves target file paths relative to repo root.

    Args:
        repo_root: Root directory of the repository.

    Returns:
        UpdatePaths: Resolved file paths for update operations.
    """
    return UpdatePaths(
        repo_root=repo_root,
        chat_page=repo_root / "spartan-hq" / "app" / "(app)" / "chat" / "page.tsx",
        message_bubble=repo_root
        / "spartan-hq"
        / "components"
        / "chat"
        / "MessageBubble.tsx",
    )


def ensure_parent_dir(path: Path) -> None:
    """Ensures the parent directory of a file exists.

    Args:
        path: File path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)


def read_text_if_exists(path: Path) -> Optional[str]:
    """Reads a text file if it exists.

    Args:
        path: File path.

    Returns:
        The file content if exists; otherwise None.

    Raises:
        OSError: If file exists but cannot be read.
    """
    if not path.exists():
        return None
    return path.read_text(encoding=ENCODING)


def backup_file(path: Path) -> None:
    """Creates a backup of a file if it exists.

    Args:
        path: File path.

    Raises:
        OSError: If backup operation fails.
    """
    if not path.exists():
        return
    backup_path = Path(str(path) + BACKUP_SUFFIX)
    shutil.copy2(path, backup_path)


def write_text_atomic(path: Path, content: str) -> None:
    """Writes text content to a file atomically.

    Args:
        path: Target file path.
        content: File content.

    Raises:
        OSError: If writing fails.
    """
    ensure_parent_dir(path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding=ENCODING)
    os.replace(tmp_path, path)


def generate_message_bubble_tsx() -> str:
    """Generates the MessageBubble.tsx component source.

    Returns:
        TSX source code as a string.
    """
    return """'use client';

import React, { useMemo, useState } from 'react';

type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

type ToolCall = {
  id?: string;
  name?: string;
  function?: { name?: string; arguments?: string };
  arguments?: string | JsonValue;
  args?: string | JsonValue;
};

type ToolResult = {
  tool_call_id?: string;
  toolCallId?: string;
  id?: string;
  name?: string;
  output?: unknown;
  result?: unknown;
  content?: unknown;
  error?: unknown;
  is_error?: boolean;
  status?: 'running' | 'success' | 'error' | string;
};

export type ChatMessage = {
  id?: string;
  role: string;
  content?: string;
  tool_calls?: ToolCall[];
  toolCalls?: ToolCall[];
  tool_results?: ToolResult[];
  toolResults?: ToolResult[];
};

const MAX_PREVIEW_CHARS = 240;

function safeJsonParse(input: string): unknown {
  try {
    return JSON.parse(input);
  } catch {
    return null;
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (typeof value !== 'object' || value === null) return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

function toDisplayString(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function normalizeToolCalls(message: ChatMessage): ToolCall[] {
  const raw = (message.tool_calls ?? message.toolCalls ?? []) as ToolCall[];
  if (!Array.isArray(raw)) return [];
  return raw.filter(Boolean);
}

function normalizeToolResults(message: ChatMessage): ToolResult[] {
  const raw = (message.tool_results ?? message.toolResults ?? []) as ToolResult[];
  if (!Array.isArray(raw)) return [];
  return raw.filter(Boolean);
}

function getToolCallId(call: ToolCall, index: number): string {
  const id = call.id ?? (call as { tool_call_id?: string }).tool_call_id;
  if (id && typeof id === 'string') return id;
  return `call_${index}`;
}

function getToolName(call: ToolCall): string {
  const fnName = call.function?.name;
  if (fnName && typeof fnName === 'string') return fnName;
  if (call.name && typeof call.name === 'string') return call.name;
  return 'tool';
}

function getToolArgs(call: ToolCall): unknown {
  const fnArgs = call.function?.arguments;
  if (typeof fnArgs === 'string' && fnArgs.trim().length > 0) {
    const parsed = safeJsonParse(fnArgs);
    return parsed ?? fnArgs;
  }
  const args = call.arguments ?? call.args;
  if (typeof args === 'string') {
    const parsed = safeJsonParse(args);
    return parsed ?? args;
  }
  return args ?? null;
}

function isErrorResult(result: ToolResult): boolean {
  if (result.is_error === true) return true;
  if (result.status && String(result.status).toLowerCase() === 'error') return true;
  if (result.error !== undefined && result.error !== null) return true;
  return false;
}

function getResultPayload(result: ToolResult): unknown {
  if (result.output !== undefined) return result.output;
  if (result.result !== undefined) return result.result;
  if (result.content !== undefined) return result.content;
  if (result.error !== undefined) return result.error;
  return result;
}

function matchResultForCall(results: ToolResult[], call: ToolCall, index: number): ToolResult | null {
  const callId = getToolCallId(call, index);
  const callName = getToolName(call);
  const byId = results.find((r) => {
    const rid = r.tool_call_id ?? r.toolCallId ?? r.id;
    return typeof rid === 'string' && rid === callId;
  });
  if (byId) return byId;

  const byName = results.find((r) => {
    if (!r.name) return false;
    return String(r.name) === callName;
  });
  return byName ?? null;
}

function ToolBadge(): JSX.Element {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-slate-300 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-700">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" className="text-slate-600">
        <path
          d="M14.7 6.3a1 1 0 0 1 0 1.4l-6 6a1 1 0 0 1-1.4-1.4l6-6a1 1 0 0 1 1.4 0ZM17 4h3v3"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M20 8a8 8 0 1 1-4.6-7.3"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
      Tool
    </span>
  );
}

function Spinner(): JSX.Element {
  return (
    <svg className="h-4 w-4 animate-spin text-slate-500" viewBox="0 0 24 24" fill="none" aria-label="Loading">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path
        className="opacity-75"
        d="M22 12a10 10 0 0 1-10 10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

function StructuredDataRenderer(props: { value: unknown }): JSX.Element {
  const { value } = props;

  const normalized = useMemo(() => {
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
        const parsed = safeJsonParse(trimmed);
        if (parsed !== null) return parsed;
      }
    }
    return value;
  }, [value]);

  if (Array.isArray(normalized)) {
    const arr = normalized as unknown[];
    const allObjects = arr.length > 0 && arr.every((row) => isPlainObject(row));
    if (allObjects) {
      const keys = Array.from(
        arr.reduce<Set<string>>((acc, row) => {
          Object.keys(row as Record<string, unknown>).forEach((k) => acc.add(k));
          return acc;
        }, new Set<string>())
      );

      return (
        <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
          <table className="min-w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-700">
              <tr>
                {keys.map((k) => (
                  <th key={k} className="whitespace-nowrap px-3 py-2 font-semibold">
                    {k}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 text-slate-800">
              {arr.map((row, idx) => (
                <tr key={idx}>
                  {keys.map((k) => (
                    <td key={k} className="whitespace-nowrap px-3 py-2 align-top">
                      <span className="font-mono">{toDisplayString((row as Record<string, unknown>)[k])}</span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    return (
      <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800">
        {toDisplayString(arr)}
      </pre>
    );
  }

  if (isPlainObject(normalized)) {
    return (
      <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800">
        {toDisplayString(normalized)}
      </pre>
    );
  }

  const str = toDisplayString(normalized);
  if (str.length > MAX_PREVIEW_CHARS && str.includes('\\n')) {
    return (
      <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800">
        {str}
      </pre>
    );
  }

  return <span className="font-mono text-xs text-slate-800">{str}</span>;
}

function ToolPanel(props: { toolCalls: ToolCall[]; toolResults: ToolResult[] }): JSX.Element {
  const { toolCalls, toolResults } =