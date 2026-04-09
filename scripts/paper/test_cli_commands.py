"""Test each agentic CLI command to diagnose failures.

Usage:
  uv run python scripts/paper/test_cli_commands.py
"""

import os
import shlex
import subprocess
import sys
import tempfile

# Minimal test prompt
TEST_PROMPT = "Reply with exactly: hello world"

# CLI commands from zero_shot_agentic_cli.py (line 119-123)
CLI_COMMANDS = {
    "claude_code": "claude --model claude-opus-4-6 -p {prompt} --output-format json --dangerously-skip-permissions",
    "codex": "codex exec --json --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --model gpt-5.2-codex -c reasoning_effort=high {prompt}",
    "gemini_cli": "gemini --model gemini-3.1-pro-preview -p {prompt} --output-format json --yolo",
}

# Env vars to strip from the parent env
_STRIP_ENV_VARS = {
    "VIRTUAL_ENV",
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_OAUTH_TOKEN",
}


def sandbox_env() -> dict[str, str]:
    """Build a sandbox env: strip vars that interfere with CLI auth/nesting."""
    return {k: v for k, v in os.environ.items() if k not in _STRIP_ENV_VARS}


def test_cli(name: str, command_template: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"Testing: {name}")
    print(f"{'=' * 60}")

    # Check if the CLI binary exists
    binary = command_template.split()[0]
    which_result = subprocess.run(["which", binary], capture_output=True, text=True)
    if which_result.returncode != 0:
        print(f"  SKIP: '{binary}' not found on PATH")
        return
    print(f"  Binary: {which_result.stdout.strip()}")

    # Build command the same way the benchmark does (line 462-465)
    _placeholder = "__PROMPT_PLACEHOLDER__"
    template_with_placeholder = command_template.replace("{prompt}", _placeholder)
    cmd_parts = shlex.split(template_with_placeholder)
    cmd = [TEST_PROMPT if part == _placeholder else part for part in cmd_parts]

    print(f"  Command: {' '.join(cmd[:6])}... (prompt truncated)")

    # Run in a temp directory (simulating sandbox)
    with tempfile.TemporaryDirectory() as tmpdir:
        env = sandbox_env()
        print(f"  CWD: {tmpdir}")
        print(f"  Stripped env vars: {_STRIP_ENV_VARS}")
        print(f"  ANTHROPIC_API_KEY present: {'ANTHROPIC_API_KEY' in env}")

        try:
            result = subprocess.run(
                cmd,
                cwd=tmpdir,
                capture_output=True,
                text=True,
                env=env,
                timeout=60,
            )
            print(f"  Exit code: {result.returncode}")
            stdout_preview = result.stdout[:500]
            print(f"  Stdout (first 500 chars): {stdout_preview}")
            if result.stderr:
                print(f"  Stderr (first 500 chars): {result.stderr[:500]}")
            if result.returncode == 0:
                print("  RESULT: SUCCESS")
            else:
                print(f"  RESULT: FAILED (exit code {result.returncode})")
        except subprocess.TimeoutExpired:
            print("  RESULT: TIMEOUT after 60s")
        except Exception as exc:
            print(f"  RESULT: EXCEPTION: {exc}")


def main():
    print("Testing agentic CLI commands")
    print(f"Python: {sys.executable}")

    # Show relevant env vars
    for var in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"]:
        val = os.environ.get(var, "")
        if val:
            print(f"  {var}: {val[:8]}...{val[-4:]}")
        else:
            print(f"  {var}: NOT SET")

    # Only test the CLIs specified on command line, or all if none specified
    cli_names = sys.argv[1:] if len(sys.argv) > 1 else list(CLI_COMMANDS.keys())
    for name in cli_names:
        if name not in CLI_COMMANDS:
            print(f"  Unknown CLI: {name}")
            continue
        test_cli(name, CLI_COMMANDS[name])

    print(f"\n{'=' * 60}")
    print("Done")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
