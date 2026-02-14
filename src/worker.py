from faster_whisper import WhisperModel
import os

MAX_CONCURRENCY = 1
MODEL_NAME = "large-v3"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE_TYPE)

def transcrever_job(path: str, language: str | None, beam_size: int) -> dict:
    try:
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

        text = "".join(text_parts).strip()
        return {
            "text": text,
            "language": info.language,
            "language_probability": float(info.language_probability),
            "segments": seg_list,
            "model": MODEL_NAME,
            "device": DEVICE,
            "compute_type": COMPUTE_TYPE,
        }
    finally:
        # o worker apaga o arquivo quando terminar (sucesso ou erro)
        try:
            os.remove(path)
        except OSError:
            pass