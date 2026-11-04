
import os
import tempfile
import redis

from flask import Flask, request, jsonify
from rq import Queue
from rq.job import Job

# Configurações
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/data/audio_uploads")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", 2048))

# Limites de processamento
JOB_TIMEOUT = int(os.getenv("JOB_TIMEOUT", 21600)) 

os.makedirs(UPLOAD_DIR, exist_ok=True)

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=0,
    decode_responses=False
)

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

q = Queue("whisper", connection=r)


def _get_bearer_token():
    auth = request.headers.get("Authorization", "")

    if not auth.startswith("Bearer "):
        return None

    return auth.removeprefix("Bearer ").strip()


def exigir_api_key():
    token = _get_bearer_token()

    if not token:
        return jsonify({
            "error": "Token ausente"
        }), 401

    if not r.exists(f"api:keys:{token}"):
        return jsonify({
            "error": "API key inválida"
        }), 403

    return None


def salvar_upload(file_storage):
    filename = file_storage.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    if not ext:
        ext = ".audio"

    fd, path = tempfile.mkstemp(
        prefix="whisper_",
        suffix=ext,
        dir=UPLOAD_DIR
    )

    os.close(fd)

    try:
        file_storage.save(path)
        return path

    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise


@app.errorhandler(413)
def arquivo_muito_grande(error):
    return jsonify({
        "error": f"Arquivo excede o limite de {MAX_UPLOAD_MB} MB"
    }), 413


@app.route("/v1/audio/transcriptions", methods=["POST"])
def transcrever_um_arquivo():

    auth_err = exigir_api_key()

    if auth_err:
        return auth_err

    f = request.files.get("file")

    if not f or not f.filename:
        return jsonify({
            "error": "Envie o arquivo no campo 'file'."
        }), 400

    language = request.args.get("language")

    try:
        beam_size = int(request.args.get("beam_size", 5))

        if not 1 <= beam_size <= 10:
            raise ValueError

    except ValueError:
        return jsonify({
            "error": "beam_size deve ser um inteiro entre 1 e 10."
        }), 400

    path = None

    try:
        path = salvar_upload(f)

        job = q.enqueue(
            "worker.transcrever_job",
            path,
            language,
            beam_size,
            job_timeout=JOB_TIMEOUT,
            result_ttl=3600,
            failure_ttl=86400
        )

        return jsonify({
            "job_id": job.id,
            "status": job.get_status(),
            "message": "Áudio recebido e enviado para processamento."
        }), 202

    except Exception:
        if path and os.path.exists(path):
            os.remove(path)

        app.logger.exception("Erro ao enviar áudio para a fila")

        return jsonify({
            "error": "Não foi possível iniciar o processamento."
        }), 500


@app.route("/v1/audio/transcriptions/<job_id>", methods=["GET"])
def status_job(job_id):

    auth_err = exigir_api_key()

    if auth_err:
        return auth_err

    try:
        job = Job.fetch(job_id, connection=r)
    except Exception:
        return jsonify({
            "error": "job_id inválido ou expirado"
        }), 404

    status = job.get_status()

    if status == "finished":
        return jsonify({
            "status": status,
            "result": job.result
        }), 200

    if status == "failed":
        return jsonify({
            "status": status,
            "error": "Falha na transcrição."
        }), 500

    return jsonify({
        "status": status
    }), 200


@app.get("/")
def health():
    return {"ok": True}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=50000)

