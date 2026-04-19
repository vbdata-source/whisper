# Whisper STT Service - Coolify Deployment

**OpenAI-kompatible Speech-to-Text API basierend auf deinem Whisper-Fork**

---

## 🚀 Deployment in Coolify

### **1. Als neuer Service erstellen:**

1. **Coolify → New Resource → Docker Compose**
2. **Name:** `whisper-service`
3. **Repository:** `vbdata-source/whisper` (dein Fork)
4. **Compose File:** Diese `docker-compose.yml` hochladen
5. **Deploy** klicken

### **2. Files in dein Repo committen:**

**Damit Coolify beim Build alles findet:**

```bash
cd /path/to/your/whisper/fork
cp docker-compose.yml Dockerfile server.py ./
git add docker-compose.yml Dockerfile server.py
git commit -m "Add Coolify deployment files"
git push
```

---

## 📋 **Modell-Konfiguration**

**Aktuell:** `large-v3` (beste Qualität)

**Ändern:**

In `docker-compose.yml`:
```yaml
args:
  MODEL_NAME: turbo  # Optionen: tiny, base, small, medium, large, turbo, large-v3
```

**Oder via ENV:**
```yaml
environment:
  WHISPER_MODEL: turbo
```

---

## 🔗 **Nutzung von anderen Coolify-Services**

**Alle Services im `coolify`-Netzwerk können Whisper erreichen:**

### **n8n HTTP Request Node:**

```yaml
Method: POST
URL: http://whisper:8000/v1/audio/transcriptions
Authentication: None

Body:
  Content Type: Multipart Form Data
  Fields:
    - file: {{ $binary.data }}
    - model: large-v3
    - language: de

Response:
  {{ $json.text }}
```

### **OpenClaw exec:**

```bash
curl -X POST http://whisper:8000/v1/audio/transcriptions \
  -F "file=@voice_message.mp3" \
  -F "model=large-v3" \
  -F "language=de"
```

### **Node.js Script:**

```javascript
const FormData = require('form-data');
const fs = require('fs');

const form = new FormData();
form.append('file', fs.createReadStream('audio.mp3'));
form.append('model', 'large-v3');
form.append('language', 'de');

const response = await fetch('http://whisper:8000/v1/audio/transcriptions', {
  method: 'POST',
  body: form
});

const { text } = await response.json();
console.log(text);
```

---

## 🎤 **API Endpoints**

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/health` | GET | Health Check |
| `/` | GET | API Info |
| `/v1/audio/transcriptions` | POST | Speech-to-Text |
| `/v1/audio/translations` | POST | Übersetze Audio → Englisch |

---

## 📊 **Transcriptions API**

**Request:**

```bash
curl -X POST http://whisper:8000/v1/audio/transcriptions \
  -F "file=@audio.mp3" \
  -F "model=large-v3" \
  -F "language=de" \
  -F "temperature=0.0" \
  -F "response_format=json"
```

**Response:**

```json
{
  "text": "Transkribierter Text hier..."
}
```

**Response Formats:**
- `json` (default): `{"text": "..."}`
- `text`: Nur der Text
- `verbose_json`: Vollständiges Whisper-Result mit Segments, Timestamps, etc.

---

## 🌍 **Unterstützte Sprachen**

Whisper unterstützt **99 Sprachen!**

**Wichtige:**
- `de` - Deutsch
- `en` - Englisch
- `fr` - Französisch
- `es` - Spanisch
- `it` - Italienisch
- `auto` - Automatische Erkennung

**Vollständige Liste:** [tokenizer.py](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py)

---

## 🔄 **Updates**

**Bei Änderungen in deinem Fork:**

1. **Code pushen:** `git push` in deinem whisper-Fork
2. **In Coolify:** Service → **Redeploy**
3. **Coolify baut neu** mit latest Code aus deinem Repo

**Modell-Cache bleibt erhalten** (via `whisper-models` Volume)!

---

## 💾 **Volumes**

| Volume | Zweck |
|--------|-------|
| `whisper-models` | Model-Cache (large-v3 ~3GB) |
| `whisper-data` | Optional: Audio-Files Workspace |

**Model-Cache verhindert Re-Download bei jedem Redeploy!**

---

## ⚙️ **Resource Limits**

**Aktuell:**
- **CPU:** 4 Cores
- **RAM:** 8GB Limit, 4GB Reserved

**Anpassen in docker-compose.yml:**

```yaml
deploy:
  resources:
    limits:
      cpus: '8.0'    # Mehr Cores = schneller
      memory: 16G
```

**large-v3 Modell braucht ~10GB VRAM (GPU) oder ~8GB RAM (CPU)**

---

## 🐛 **Troubleshooting**

### **Container startet nicht:**

```bash
# Logs prüfen
docker logs whisper-<uuid>

# Health Check
curl http://whisper:8000/health
```

### **Out of Memory:**

Erhöhe Memory Limit oder nutze kleineres Modell (`medium`, `turbo`)

### **Langsame Transkription:**

- **GPU nutzen** (falls verfügbar): Docker mit `--gpus all`
- **Kleineres Modell:** `turbo` statt `large-v3`
- **Mehr CPU Cores:** Erhöhe `cpus` Limit

---

## 📚 **Beispiel: Telegram Voice-Message-Bot**

**n8n Workflow:**

```
1. Telegram Trigger (Voice Message)
   ↓
2. Download Audio (Telegram → n8n)
   ↓
3. HTTP Request → Whisper
   URL: http://whisper:8000/v1/audio/transcriptions
   Body: file + model=large-v3 + language=de
   ↓
4. Telegram Reply (Transkription senden)
```

---

## 🔗 **Referenzen**

- **Dein Fork:** https://github.com/vbdata-source/whisper
- **OpenAI Whisper:** https://github.com/openai/whisper
- **Whisper Paper:** https://arxiv.org/abs/2212.04356
- **Modell-Performance:** https://github.com/openai/whisper#available-models-and-languages

---

*Erstellt: 2026-04-19*
*Model: large-v3 (beste Qualität)*
