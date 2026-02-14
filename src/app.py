import os
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


MAX_CONCURRENCY = 1
MODEL_NAME = "large-v3"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

app = Flask(__name__)
q = Queue("whisper", connection=r)

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

    language = request.args.get("language")  # pode ser None
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

    return jsonify({"job_id": job.id, "status": job.get_status()}), 202

@app.route("/v1/audio/transcriptions/<job_id>", methods=["GET"])
def status_job(job_id):
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
