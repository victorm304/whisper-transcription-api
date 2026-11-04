
import os
import logging
from faster_whisper import WhisperModel

# Configurações
MODEL_NAME = os.getenv("WHISPER_MODEL", "large-v3")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

BEAM_SIZE_DEFAULT = int(os.getenv("WHISPER_BEAM_SIZE", "5"))

# Logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger("whisper-worker")

# Carrega o modelo uma única vez quando o worker inicia
logger.info(
    "Carregando modelo %s | device=%s | compute_type=%s",
    MODEL_NAME,
    DEVICE,
    COMPUTE_TYPE
)

model = WhisperModel(
    MODEL_NAME,
    device=DEVICE,
    compute_type=COMPUTE_TYPE
)

logger.info("Modelo carregado com sucesso")


def transcrever_job(
    path: str,
    language: str | None = None,
    beam_size: int = BEAM_SIZE_DEFAULT
) -> dict:

    if not os.path.isfile(path):
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    try:
        logger.info("Iniciando transcrição: %s", path)

        segments, info = model.transcribe(
            path,
            task="transcribe",
            language=language,
            beam_size=beam_size,

            # Voice Activity Detection
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 500,
                "speech_pad_ms": 200,
            },

            # Evita manter contexto excessivo entre janelas
            condition_on_previous_text=False,

            # Evita timestamps de palavras desnecessários
            word_timestamps=False,
        )

        seg_list = []
        text_parts = []

        # A transcrição é executada durante a iteração
        for s in segments:

            segment_text = s.text.strip()

            seg_list.append({
                "start": round(float(s.start), 3),
                "end": round(float(s.end), 3),
                "text": segment_text
            })

            if segment_text:
                text_parts.append(segment_text)

        text = " ".join(text_parts)

        result = {
            "text": text,
            "language": info.language,
            "language_probability": float(info.language_probability),
            "duration": float(info.duration),
            "segments": seg_list,
            "model": MODEL_NAME,
            "device": DEVICE,
            "compute_type": COMPUTE_TYPE,
        }

        logger.info(
            "Transcrição concluída: %.2f minutos | %d segmentos",
            info.duration / 60,
            len(seg_list)
        )

        return result

    except Exception:
        logger.exception("Erro durante transcrição: %s", path)
        raise

    finally:
        # Remove o arquivo após sucesso ou falha
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info("Arquivo temporário removido: %s", path)

        except OSError:
            logger.exception("Não foi possível remover: %s", path)

