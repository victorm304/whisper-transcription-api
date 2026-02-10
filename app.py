import os
import tempfile
from flask import Flask, request, jsonify
from faster_whisper import WhisperModel
from threading import BoundedSemaphore

MAX_CONCURRENCY = 1
MODEL_NAME = "large-v3"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

app = Flask(__name__)
sem = BoundedSemaphore(value=MAX_CONCURRENCY)

model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE_TYPE)


def _salvar_upload_temporario(file_storage) -> str:
    filename = file_storage.filename or ""
    _, ext = os.path.splitext(filename)
    ext = ext if ext else ".bin"

    fd, path = tempfile.mkstemp(prefix="audio_", suffix=ext)
    os.close(fd)

    file_storage.save(path)
    return path


def _transcrever_path(path: str, language: str | None, beam_size: int) -> dict:
    segments, info = model.transcribe(
        path,
        task="transcribe",
        language=language,     # "pt" ou None (auto)
        beam_size=beam_size,
        vad_filter=True,
    )

    seg_list = []
    text_parts = []
    for s in segments:
        seg_list.append({"start": float(s.start), "end": float(s.end), "text": s.text})
        text_parts.append(s.text)

    return {
        "text": "".join(text_parts).strip(),
        "language": info.language,
        "language_probability": float(info.language_probability),
        "segments": seg_list,
        "model": MODEL_NAME,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
    }


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

    acquired = sem.acquire(blocking=False)
    if not acquired:
        return jsonify({"error": "Servidor ocupado. Tente novamente em instantes."}), 429

    path = None
    try:
        path = _salvar_upload_temporario(f)
        res = _transcrever_path(path=path, language=language, beam_size=beam_size)
        return jsonify(res)
    
    except Exception as e:
        return jsonify({"error": "Erro interno ao processar áudio"}), 500
    finally:
        sem.release()
        if path:
            try:
                os.remove(path)
            except OSError:
                pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=50000)
