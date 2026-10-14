#!/usr/bin/env python3
"""Example model adapter for CTXGAP evaluation.

Contract: read the prompt from stdin, write the model answer to stdout.
`evaluate.py` will parse the first JSON object found in stdout.

This example uses the Anthropic Messages API. Replace it with any backend
(OpenAI, vLLM, a local model, your own gateway) as long as the contract holds.

    pip install anthropic
    export ANTHROPIC_API_KEY=...
    export CTXGAP_EVAL_CMD='python3 scripts/my_model_adapter.py'
    export CTXGAP_EVAL_MODEL=claude-sonnet-4-5
    python3 scripts/evaluate.py --view U --limit 2
"""
import json, os, sys

MODEL = os.environ.get("CTXGAP_EVAL_MODEL", "claude-sonnet-4-5")
SYSTEM_HINT = ""  # the frozen observer system prompt is already in the user message


def main():
    prompt = sys.stdin.read()
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model=MODEL, max_tokens=8000,
            system="You answer strictly from the material provided.",
            messages=[{"role": "user", "content": prompt}])
        out = msg.content[0].text if msg.content else ""
    except Exception as e:          # fall back to echoing an empty JSON object
        print(json.dumps({"error": str(e)[:200]}), file=sys.stderr)
        out = "{}"
    print(out)


if __name__ == "__main__":
    main()
