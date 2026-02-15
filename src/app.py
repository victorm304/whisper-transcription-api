import os
import base64
import hashlib
import tempfile
import redis
from flask import Flask, request, jsonify
from rq import Queue
from rq.job import Job

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "127.0.0.1"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0
)

PEPPER = os.getenv("JOB_TOKEN_PEPPER", "troque-isto-em-producao")

app = Flask(__name__)
q = Queue("whisper", connection=r)


def gerar_token() -> str:
    raw = os.urandom(32)
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def hash_token(token: str) -> str:
    return hashlib.sha256((token + PEPPER).encode()).hexdigest()


def salvar_token_job(r, job_id: str, token: str, ttl_sec: int = 60 * 5):
    key = f"job:{job_id}:token_hash"
    r.setex(key, ttl_sec, hash_token(token))


def validar_token_job(r, job_id: str, token_recebido: str) -> bool:
    key = f"job:{job_id}:token_hash"
    esperado = r.get(key)
    if not esperado:
        return False
    return esperado.decode() == hash_token(token_recebido)


def _salvar_upload_temporario(file_storage) -> str:
    filename = file_storage.filename or ""
    _, ext = os.path.splitext(filename)
    ext = ext if ext else ".bin"

    fd, path = tempfile.mkstemp(prefix="audio_", suffix=ext)
    os.close(fd)

    file_storage.save(path)
    return path


@app.route("/v1/audio/transcriptions", methods=["POST"])
def transcrever_um_arquivo():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "Envie o arquivo em form-data com o campo 'file'."}), 400

    language = request.args.get("language")
    beam_size_str = request.args.get("beam_size", "10")

    try:
        beam_size = int(beam_size_str)
    except ValueError:
        return jsonify({"error": "beam_size precisa ser um inteiro."}), 400

    path = _salvar_upload_temporario(f)

    job = q.enqueue(
        "worker.transcrever_job",
        path,
        language,
        beam_size,
        job_timeout=60 * 20,
        result_ttl=60 * 5,
    )

    token = gerar_token()
    salvar_token_job(r, job.id, token, ttl_sec=60 * 5)

    return jsonify({
        "job_id": job.id,
        "status": job.get_status(),
        "token": token 
    }), 202


@app.route("/v1/audio/transcriptions/<job_id>", methods=["GET"])
def status_job(job_id):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"error": "Token ausente"}), 401

    token = auth.removeprefix("Bearer ").strip()

    if not validar_token_job(r, job_id, token):
        return jsonify({"error": "Token inválido ou expirado"}), 403

    try:
        job = Job.fetch(job_id, connection=r)
    except Exception:
        return jsonify({"error": "job_id inválido ou expirado"}), 404

    status = job.get_status()

    if status == "finished":
        return jsonify({"status": status, "result": job.result}), 200

    if status == "failed":
        return jsonify({"status": status, "error": "job falhou (veja logs do worker)"}), 500

    return jsonify({"status": status}), 200


@app.get("/")
def health():
    return {"ok": True}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=50000)
