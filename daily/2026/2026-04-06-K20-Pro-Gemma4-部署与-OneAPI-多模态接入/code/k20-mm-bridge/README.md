# K20 multimodal bridge

Minimal OpenAI-compatible bridge for `one-api`.

Supported now:

- `GET /healthz`
- `GET /v1/models`
- `POST /v1/chat/completions`
- single image only
- `stream=false` only

Behavior:

- text-only requests fall back to Ollama on the phone
- image requests call `llama-mtmd-cli` over SSH on the phone
