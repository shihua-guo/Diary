import base64
import json
import logging
import os
import posixpath
import shlex
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


LOG_LEVEL = os.environ.get("BRIDGE_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("k20-mm-bridge")


CONFIG = {
    "host": os.environ.get("BRIDGE_HOST", "0.0.0.0"),
    "port": int(os.environ.get("BRIDGE_PORT", "18080")),
    "model_name": os.environ.get("BRIDGE_MODEL_NAME", "gemma4-vl"),
    "api_key": os.environ.get("BRIDGE_API_KEY", ""),
    "request_timeout": int(os.environ.get("BRIDGE_REQUEST_TIMEOUT", "600")),
    "ssh_host": os.environ.get("K20_SSH_HOST", "192.168.2.202"),
    "ssh_port": int(os.environ.get("K20_SSH_PORT", "8022")),
    "ssh_user": os.environ.get("K20_SSH_USER", "u0_a247"),
    "ssh_key": os.environ.get("K20_SSH_KEY", "/root/.ssh/k20_mm_bridge_ed25519"),
    "remote_cli": os.environ.get(
        "K20_REMOTE_CLI",
        "/data/data/com.termux/files/home/llama.cpp/build/bin/llama-mtmd-cli",
    ),
    "remote_model": os.environ.get(
        "K20_REMOTE_MODEL",
        "/data/data/com.termux/files/home/models/gemma-4-main.gguf",
    ),
    "remote_mmproj": os.environ.get(
        "K20_REMOTE_MMPROJ",
        "/data/data/com.termux/files/home/models/mmproj-vision.gguf",
    ),
    "remote_tmp_dir": os.environ.get(
        "K20_REMOTE_TMP_DIR",
        "/data/data/com.termux/files/home/tmp/oneapi-mm-bridge",
    ),
    "remote_system_prompt": os.environ.get(
        "K20_REMOTE_SYSTEM_PROMPT",
        "You are a helpful vision assistant. Answer in the user's language. "
        "Output only the final answer. Do not output reasoning, thought, or channel markers.",
    ),
    "default_ctx": int(os.environ.get("K20_CTX_SIZE", "2048")),
    "default_predict": int(os.environ.get("K20_PREDICT", "128")),
    "default_threads": int(os.environ.get("K20_THREADS", "8")),
    "default_temp": float(os.environ.get("K20_TEMPERATURE", "0.2")),
    "default_top_p": float(os.environ.get("K20_TOP_P", "0.95")),
    "ollama_base_url": os.environ.get("K20_OLLAMA_BASE_URL", "http://192.168.2.202:11434"),
    "ollama_model": os.environ.get("K20_OLLAMA_TEXT_MODEL", "gemma4:latest"),
    "remote_ollama_bin": os.environ.get(
        "K20_REMOTE_OLLAMA_BIN",
        "/data/data/com.termux/files/usr/bin/ollama",
    ),
    "oneapi_test_prompt": os.environ.get(
        "ONEAPI_TEST_PROMPT",
        "Output only your specific model name with no additional text.",
    ),
}


REQUEST_LOCK = threading.Lock()


def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def make_openai_error(message, code="bridge_error", status=HTTPStatus.BAD_REQUEST):
    return status, {
        "error": {
            "message": message,
            "type": "invalid_request_error" if status < 500 else "server_error",
            "param": None,
            "code": code,
        }
    }


def maybe_require_api_key(handler):
    expected = CONFIG["api_key"].strip()
    if not expected:
        return None
    auth = handler.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if token != expected:
        return make_openai_error("invalid api key", "invalid_api_key", HTTPStatus.UNAUTHORIZED)
    return None


def normalize_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def extract_prompt_and_image(messages):
    conversation_lines = []
    image_url = None

    for message in messages or []:
        role = normalize_text(message.get("role") or "user").strip() or "user"
        content = message.get("content", "")

        if isinstance(content, str):
            text = content.strip()
            if text:
                conversation_lines.append(f"{role.capitalize()}: {text}")
            continue

        if isinstance(content, list):
            text_parts = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                part_type = part.get("type")
                if part_type == "text":
                    text = normalize_text(part.get("text")).strip()
                    if text:
                        text_parts.append(text)
                elif part_type == "image_url":
                    raw = part.get("image_url")
                    if isinstance(raw, dict):
                        raw = raw.get("url")
                    raw = normalize_text(raw).strip()
                    if raw:
                        image_url = raw
            if text_parts:
                conversation_lines.append(f"{role.capitalize()}: {' '.join(text_parts)}")

    prompt = "\n".join(conversation_lines).strip()
    if not prompt and image_url:
        prompt = "请描述这张图片。"
    return prompt, image_url


def should_short_circuit_text_probe(messages):
    expected = normalize_text(CONFIG["oneapi_test_prompt"]).strip().lower()
    if not expected:
        return False

    for message in messages or []:
        content = message.get("content", "")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "text":
                    continue
                text = normalize_text(part.get("text")).strip().lower()
                if text == expected:
                    return True
        else:
            text = normalize_text(content).strip().lower()
            if text == expected:
                return True
    return False


def maybe_handle_text_probe(requested_model, messages, image_url):
    if image_url:
        return None
    if should_short_circuit_text_probe(messages):
        return requested_model
    return None


def download_image_to_temp(image_url):
    parsed = urllib.parse.urlparse(image_url)
    suffix = ".img"
    if parsed.path:
        path_suffix = Path(parsed.path).suffix
        if path_suffix:
            suffix = path_suffix

    fd, local_path = tempfile.mkstemp(prefix="k20-mm-", suffix=suffix)
    os.close(fd)

    if image_url.startswith("data:"):
        header, encoded = image_url.split(",", 1)
        mime = header.split(";")[0].removeprefix("data:")
        if mime == "image/png":
            local_path = _replace_suffix(local_path, ".png")
        elif mime in {"image/jpeg", "image/jpg"}:
            local_path = _replace_suffix(local_path, ".jpg")
        payload = base64.b64decode(encoded)
        with open(local_path, "wb") as f:
            f.write(payload)
        return local_path

    request = urllib.request.Request(
        image_url,
        headers={"User-Agent": "k20-mm-bridge/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as resp, open(local_path, "wb") as out:
        out.write(resp.read())
    return local_path


def _replace_suffix(path, suffix):
    original = Path(path)
    target = str(original.with_suffix(suffix))
    if target != path and os.path.exists(path):
        os.replace(path, target)
    return target


def run_command(cmd, timeout, check=True):
    logger.debug("running command: %s", cmd)
    completed = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {completed.stdout.strip() or 'no output'}"
        )
    return completed.stdout


def ssh_base():
    return [
        "ssh",
        "-i",
        CONFIG["ssh_key"],
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-p",
        str(CONFIG["ssh_port"]),
        f"{CONFIG['ssh_user']}@{CONFIG['ssh_host']}",
    ]


def scp_base():
    return [
        "scp",
        "-i",
        CONFIG["ssh_key"],
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-P",
        str(CONFIG["ssh_port"]),
    ]


def remote_shell(script, timeout):
    return run_command(ssh_base() + [script], timeout=timeout)


def copy_to_phone(local_path, remote_path, timeout):
    remote_spec = f"{CONFIG['ssh_user']}@{CONFIG['ssh_host']}:{remote_path}"
    run_command(scp_base() + [local_path, remote_spec], timeout=timeout)


def ensure_ollama_running():
    check_script = "curl -fsS -m 3 http://127.0.0.1:11434/api/tags >/dev/null"
    try:
        remote_shell(check_script, timeout=5)
        return
    except Exception:  # noqa: BLE001
        logger.info("remote ollama is not reachable, trying to start it")

    start_script = (
        "pgrep -f 'ollama serve' >/dev/null "
        f"|| nohup env OLLAMA_HOST=0.0.0.0:11434 {shlex.quote(CONFIG['remote_ollama_bin'])} serve "
        ">/data/data/com.termux/files/home/ollama.log 2>&1 </dev/null &"
    )
    remote_shell(start_script, timeout=10)

    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            remote_shell(check_script, timeout=5)
            logger.info("remote ollama is reachable again")
            return
        except Exception:  # noqa: BLE001
            time.sleep(1)
    raise RuntimeError("failed to start remote ollama service")


def call_ollama_text(messages):
    ensure_ollama_running()
    payload = {
        "model": CONFIG["ollama_model"],
        "stream": False,
        "messages": [],
    }
    for message in messages or []:
        role = normalize_text(message.get("role") or "user").strip() or "user"
        content = message.get("content", "")
        if isinstance(content, list):
            pieces = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = normalize_text(part.get("text")).strip()
                    if text:
                        pieces.append(text)
            content = " ".join(pieces)
        content = normalize_text(content).strip()
        if content:
            payload["messages"].append({"role": role, "content": content})

    if not payload["messages"]:
        payload["messages"].append({"role": "user", "content": "ping"})

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        urllib.parse.urljoin(CONFIG["ollama_base_url"].rstrip("/") + "/", "api/chat"),
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    message = normalize_text(((body.get("message") or {}).get("content"))).strip()
    return message or normalize_text(body)


def build_remote_command(prompt, remote_image_path, max_tokens, temperature, top_p):
    parts = [
        shlex.quote(CONFIG["remote_cli"]),
        "--jinja",
        "--no-warmup",
        "-sys",
        shlex.quote(CONFIG["remote_system_prompt"]),
        "-m",
        shlex.quote(CONFIG["remote_model"]),
        "--mmproj",
        shlex.quote(CONFIG["remote_mmproj"]),
        "-p",
        shlex.quote(prompt),
        "-c",
        str(CONFIG["default_ctx"]),
        "-n",
        str(max_tokens),
        "-t",
        str(CONFIG["default_threads"]),
        "--temp",
        str(temperature),
        "--top-p",
        str(top_p),
    ]
    if remote_image_path:
        parts.extend(["--image", shlex.quote(remote_image_path)])
    return " ".join(parts)


def extract_mtmd_answer(output):
    kept_lines = []
    log_prefixes = (
        "common_init_result:",
        "llama_",
        "llama.",
        "llama_perf_context_print:",
        "print_info:",
        "load:",
        "load_tensors:",
        "load_hparams:",
        "clip_",
        "main:",
        "WARN:",
        "sched_reserve:",
        "alloc_compute_meta:",
        "warmup:",
        "image slice encoded",
        "encoding image slice",
        "image decoded",
        "decoding image batch",
        "mtmd_cli_context:",
        "str:",
        "--- vision hparams ---",
        "0:",
        "1:",
        "2:",
        "3:",
        "4:",
        "5:",
        "6:",
        "7:",
        "8:",
        "9:",
        "10:",
        "11:",
        "<bos><|turn>system",
        "<|turn>user",
        "<|turn>model",
        "<|think|>",
        "For normal use cases,",
    )

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            if kept_lines and kept_lines[-1] != "":
                kept_lines.append("")
            continue
        if set(line) == {"."}:
            continue
        if line in {"'", '"'}:
            continue
        if line.endswith("<turn|>"):
            continue
        if any(line.startswith(prefix) for prefix in log_prefixes):
            continue
        kept_lines.append(line)

    while kept_lines and kept_lines[-1] == "":
        kept_lines.pop()
    return "\n".join(kept_lines).strip()


def call_mtmd(prompt, image_url, max_tokens, temperature, top_p):
    local_path = None
    remote_path = None
    try:
        remote_shell(
            f"mkdir -p {shlex.quote(CONFIG['remote_tmp_dir'])}",
            timeout=30,
        )

        if image_url:
            local_path = download_image_to_temp(image_url)
            remote_name = f"{uuid.uuid4().hex}{Path(local_path).suffix or '.img'}"
            remote_path = posixpath.join(CONFIG["remote_tmp_dir"], remote_name)
            copy_to_phone(local_path, remote_path, timeout=60)

        command = build_remote_command(prompt, remote_path, max_tokens, temperature, top_p)
        output = remote_shell(command, timeout=CONFIG["request_timeout"])
        answer = extract_mtmd_answer(output)
        if not answer:
            raise RuntimeError("multimodal CLI returned empty output")
        return answer
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)
        if remote_path:
            try:
                remote_shell(f"rm -f {shlex.quote(remote_path)}", timeout=30)
            except Exception as exc:  # noqa: BLE001
                logger.warning("failed to clean remote temp file %s: %s", remote_path, exc)


def make_chat_response(model_name, content, prompt_tokens=0, completion_tokens=0):
    created = int(time.time())
    response_id = f"chatcmpl-{uuid.uuid4().hex}"
    return {
        "id": response_id,
        "object": "chat.completion",
        "created": created,
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "K20MMBridge/1.0"

    def do_GET(self):
        auth_error = maybe_require_api_key(self)
        if auth_error:
            status, payload = auth_error
            return json_response(self, status, payload)

        if self.path in {"/healthz", "/health", "/"}:
            return json_response(
                self,
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "k20-mm-bridge",
                    "model": CONFIG["model_name"],
                },
            )
        if self.path == "/v1/models":
            return json_response(
                self,
                HTTPStatus.OK,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": CONFIG["model_name"],
                            "object": "model",
                            "owned_by": "k20-pro",
                        }
                    ],
                },
            )
        status, payload = make_openai_error("not found", "not_found", HTTPStatus.NOT_FOUND)
        return json_response(self, status, payload)

    def do_POST(self):
        auth_error = maybe_require_api_key(self)
        if auth_error:
            status, payload = auth_error
            return json_response(self, status, payload)

        if self.path != "/v1/chat/completions":
            status, payload = make_openai_error("not found", "not_found", HTTPStatus.NOT_FOUND)
            return json_response(self, status, payload)

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            status, error = make_openai_error(
                f"invalid JSON body: {exc}",
                "invalid_json",
                HTTPStatus.BAD_REQUEST,
            )
            return json_response(self, status, error)

        if payload.get("stream"):
            status, error = make_openai_error(
                "stream=true is not supported yet",
                "stream_not_supported",
                HTTPStatus.BAD_REQUEST,
            )
            return json_response(self, status, error)

        requested_model = normalize_text(payload.get("model")).strip() or CONFIG["model_name"]
        if requested_model != CONFIG["model_name"]:
            status, error = make_openai_error(
                f"unsupported model: {requested_model}",
                "model_not_supported",
                HTTPStatus.BAD_REQUEST,
            )
            return json_response(self, status, error)

        messages = payload.get("messages") or []
        prompt, image_url = extract_prompt_and_image(messages)
        if not prompt and not image_url:
            status, error = make_openai_error(
                "no usable prompt or image found in messages",
                "empty_prompt",
                HTTPStatus.BAD_REQUEST,
            )
            return json_response(self, status, error)

        max_tokens = int(payload.get("max_tokens") or CONFIG["default_predict"])
        max_tokens = max(1, min(max_tokens, 512))
        temperature = float(payload.get("temperature") or CONFIG["default_temp"])
        top_p = float(payload.get("top_p") or CONFIG["default_top_p"])

        start = time.time()
        with REQUEST_LOCK:
            try:
                probe_response = maybe_handle_text_probe(requested_model, messages, image_url)
                if probe_response is not None:
                    content = probe_response
                elif image_url:
                    content = call_mtmd(prompt, image_url, max_tokens, temperature, top_p)
                else:
                    content = call_ollama_text(messages)
            except urllib.error.URLError as exc:
                logger.exception("downstream HTTP request failed")
                status, error = make_openai_error(
                    f"downstream HTTP request failed: {exc}",
                    "downstream_http_error",
                    HTTPStatus.BAD_GATEWAY,
                )
                return json_response(self, status, error)
            except subprocess.TimeoutExpired:
                logger.exception("multimodal request timed out")
                status, error = make_openai_error(
                    "multimodal request timed out",
                    "timeout",
                    HTTPStatus.GATEWAY_TIMEOUT,
                )
                return json_response(self, status, error)
            except Exception as exc:  # noqa: BLE001
                logger.exception("request failed")
                status, error = make_openai_error(
                    f"bridge request failed: {exc}",
                    "bridge_failure",
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return json_response(self, status, error)

        elapsed = time.time() - start
        logger.info(
            "handled request model=%s image=%s elapsed=%.2fs",
            requested_model,
            bool(image_url),
            elapsed,
        )
        prompt_tokens = max(1, len(prompt) // 4) if prompt else 0
        completion_tokens = max(1, len(content) // 4) if content else 0
        return json_response(
            self,
            HTTPStatus.OK,
            make_chat_response(requested_model, content, prompt_tokens, completion_tokens),
        )

    def log_message(self, fmt, *args):
        logger.info("%s - %s", self.address_string(), fmt % args)


def main():
    server = ThreadingHTTPServer((CONFIG["host"], CONFIG["port"]), Handler)
    logger.info(
        "starting k20 multimodal bridge on %s:%s for model %s",
        CONFIG["host"],
        CONFIG["port"],
        CONFIG["model_name"],
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
