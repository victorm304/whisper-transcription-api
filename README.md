# Whisper Transcription API

API simples para transcrição de áudio usando **Faster-Whisper**, empacotada em Docker.

---

## Endpoint

### `POST /v1/audio/transcriptions`

**Headers (obrigatório):**
- `Authorization: Bearer <API_KEY>`

**Form-data (obrigatório):**
- `file` — arquivo de áudio

**Query params (opcionais):**
- `language` — ex: `pt`
- `beam_size` — inteiro (padrão: 10)


**Gerar Api Key**
```bash
./gen_key.sh
```

**Exemplo de uso:**

```bash
curl -X POST "http://localhost:50000/v1/audio/transcriptions?language=pt&beam_size=10" \
  -H "Authorization: Bearer <API_KEY>" \
  -F "file=@/caminho/do/audio"
```
**Depois:**

``` bash
curl -X GET "http://localhost:50000/v1/audio/transcriptions/<job_id>" \
  -H "Authorization: Bearer <API_KEY>"
```
**Instalação**

```bash
git clone https://github.com/victorm304/whisper-transcription-api/
cd whisper-transcription-api
docker compose up --build
```
