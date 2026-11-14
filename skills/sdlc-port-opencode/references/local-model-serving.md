# Local Model Serving for the OpenCode Path (llama.cpp)

Operational reference for running a local LLM behind OpenCode so the SDLC works without a hosted API (e.g. when Claude Code limits are exhausted). Focused on **llama.cpp (`llama-server`)** feeding OpenCode's OpenAI-compatible provider, on a 2× RTX 3090 / 48 GB-VRAM-class workstation.

> **Confidence / freshness:** Verified on 2026-06-27. The Qwen3.6 family and the llama.cpp tool-call bugs below were released/filed in 2026 and verified from live primary sources (HuggingFace model cards, QwenLM GitHub, Unsloth, llama.cpp issues, OpenCode docs) — not from model training knowledge. Re-verify build numbers and the model card "Best Practices" before locking in, since llama.cpp fixes land incrementally. Items marked *(unverified)* could not be confirmed from a primary source.

## Why this matters for the SDLC

z-sdlc is **instruction-following- and tool-calling-heavy**: long multi-step skills, subagent dispatch, structured gates. The dominant risk on a local model is **not** raw coding ability — it's **tool-call reliability under long prompts**. Most of this doc is about making tool calls survive that load. Treat the local model as a capable fallback for the cheaper tier of work, not a drop-in for Opus-class orchestration.

## Recommended models (Qwen3.6 family)

Both fit 48 GB and have community validation on dual 3090s + OpenCode. Official benchmark figures are from the HuggingFace model cards.

| Model | Type | Context (native) | SWE-bench Verified | LiveCodeBench v6 | Notes |
|-------|------|------------------|--------------------|------------------|-------|
| **Qwen3.6-35B-A3B** | MoE, 35B total / ~3B active | 262,144 (→~1M YaRN) | 73.4 | 80.4 | Agentic-coding tuned; fast (3B active); natively multimodal; Apache-2.0 |
| **Qwen3.6-27B** | Dense, 27B | 262,144 (→~1M YaRN) | 77.2 | 83.9 | "Flagship-level coding"; vision; Terminal-Bench 2.0 59.3; dense → steadier long-prompt instruction-following |

**Default for z-sdlc:** **Qwen3.6-35B-A3B** at Q8 — agentic-coding-tuned, fast, fits fully in VRAM.
**Reliability fallback:** **Qwen3.6-27B dense** at Q8 — if you see tool-call drift on long skill prompts, dense models track complex multi-step instructions more steadily than sparse MoE, and it has slightly higher coding scores.

*(BFCL and Aider polyglot scores were not on the cards fetched — unverified. GLM-4.5-Air remains excluded: 106B total does not fit 48 GB at any practical quant.)*

## GGUF quant selection for 48 GB

Unsloth ships Dynamic 2.0 (`UD-`) GGUFs for both. Sizes are weights-only; leave ~12–20 GB headroom for the KV cache.

**Qwen3.6-35B-A3B-GGUF** — `Q8_0` 36.9 GB · `UD-Q6_K` 29.3 GB · `UD-Q4_K_XL` 22.4 GB · `UD-Q3_K_XL` 16.8 GB
**Qwen3.6-27B-GGUF** — `Q8_0` 28.6 GB · `Q6_K` 22.5 GB · `UD-Q4_K_XL` 17.6 GB · `Q4_K_M` 16.8 GB

On 48 GB you can afford **Q8 for both** (max quality) and still keep 100K+ context with q8_0 KV cache. Drop to UD-Q6/Q4 only when you want very large context. `UD-Q4_K_XL` is Unsloth's quality/size floor.

Sources: `huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF`, `huggingface.co/unsloth/Qwen3.6-27B-GGUF`.

## llama.cpp tool-calling — the critical part

`llama-server` exposes an OpenAI-compatible `/v1/chat/completions`. Function calling **requires `--jinja`** so it applies the model's chat template. But the Qwen3.5/3.6 family has **known template bugs that break tool calls** — fix them before blaming the model:

- **Tool calls emitted inside `<think>` blocks**, and under long context with multi-optional-param tools, calls loop with a parameter always missing (llama.cpp issues #21158, #20164; PR #20424 only partial).
- **Qwen3.6-27B cache-invalidation bug** forces full-prompt reprocessing — tied to the hybrid Gated-DeltaNet/SWA memory interacting with the chat template (issue #22746; PR #24785 was still open on 2026-06-27 — check whether it has merged).

**Fix:** use a corrected chat template via `--chat-template-file`:
- **`froggeric/Qwen-Fixed-Chat-Templates`** (HF) — Qwen3.6-specific drop-in (v8/v9/v10) that removes the spurious cache invalidations and auto-closes an unclosed `<think>` before a `tool_call`. A community report had an OpenCode agent run 20+ min without a malformed-tool-call failure after switching to it *(community-reported, not a vendor benchmark)*.
- **Unsloth's updated GGUFs** also bundle tool-calling template fixes.

Most reliable single mitigation for tool-heavy runs: **disable thinking** — `--chat-template-kwargs '{"enable_thinking":false}'` (or `--reasoning-budget -1`), at some reasoning-quality cost.

## OpenCode wiring

Default `llama-server` endpoint is `http://127.0.0.1:8080/v1`. Point OpenCode at it with an `@ai-sdk/openai-compatible` provider. The `models` key must match `llama-server`'s `--alias`.

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "llama.cpp": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "llama-server (local)",
      "options": { "baseURL": "http://127.0.0.1:8080/v1" },
      "models": {
        "qwen3.6-35b-a3b": {
          "name": "Qwen3.6-35B-A3B (local)",
          "limit": { "context": 131072, "output": 65536 }
        }
      }
    }
  },
  "model": "llama.cpp/qwen3.6-35b-a3b",
  "small_model": "llama.cpp/qwen3.6-35b-a3b"
}
```

**Keep OpenCode's `limit.context` ≤ the `-c` you actually allocated.** Over-sizing context forces silent CPU fallback that degrades tool-call *format* reliability, not just speed. If tool calls don't fire, raise the served context (`-c`) and confirm the fixed template is loaded.

## Launch commands (2× RTX 3090)

**Qwen3.6-35B-A3B (MoE, Q8 — fits fully in VRAM):**
```bash
./llama-server \
  -m Qwen3.6-35B-A3B-Q8_0.gguf \
  --alias qwen3.6-35b-a3b \
  -ngl 99 --tensor-split 1,1 \
  -c 131072 -fa \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  --jinja --chat-template-file qwen3.6-fixed.jinja \
  --host 0.0.0.0 --port 8080
# Pushing -c toward 256K and out of VRAM? add: --n-cpu-moe 8  (or -ot ".ffn_.*_exps.=CPU")
```

**Qwen3.6-27B (dense, Q8):**
```bash
./llama-server \
  -m Qwen3.6-27B-Q8_0.gguf \
  --alias qwen3.6-27b \
  -ngl 99 --tensor-split 1,1 \
  -c 131072 -fa \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  --jinja --chat-template-file qwen3.6-fixed.jinja \
  --host 0.0.0.0 --port 8080
```

Flag notes: `-fa` (flash attention) is required to quantize the V cache — build with `-DGGML_CUDA_FA_ALL_QUANTS=ON`. `--cache-type-* q8_0` is the safe KV quality point; `q4_0` only for extreme context. For the MoE, expert offload (`--n-cpu-moe` / `-ot`) is **not** needed at Q8 on 48 GB — reserve it for very large context. Confirm Qwen3.6's recommended **sampling params** against the model card's "Best Practices" *(the Qwen3-Coder values — temp 0.7 / top-p 0.8 / top-k 20 / repeat-penalty 1.05 — are a reasonable start but unverified for 3.6)*.

## Reliability checklist for long agentic (z-sdlc) prompts

1. **Fixed chat template** loaded via `--chat-template-file` (froggeric or Unsloth). Non-negotiable.
2. **Disable thinking** for tool-heavy skill runs if you see calls buried in `<think>`.
3. **`limit.context` ≤ `-c`** — never over-allocate context past VRAM.
4. **Track llama.cpp build numbers** — tool-call fixes land incrementally (#20424, #24785).
5. **Prefer the dense 27B** if the MoE drifts on long multi-step skills; trade speed for steadier instruction-following.
6. Expect to **degrade gracefully**: run cheap/retrieval-tier SDLC work locally; keep orchestration-heavy skills on a stronger model when available.

## Sources

- `huggingface.co/Qwen/Qwen3.6-35B-A3B`, `huggingface.co/Qwen/Qwen3.6-27B`, `github.com/QwenLM/Qwen3.6`
- `huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF`, `huggingface.co/unsloth/Qwen3.6-27B-GGUF`, `unsloth.ai/docs/models/qwen3.6`
- `github.com/ggml-org/llama.cpp/issues/21158`, `/20164`, `/22746`
- `huggingface.co/froggeric/Qwen-Fixed-Chat-Templates`
- `opencode.ai/docs/providers/`
