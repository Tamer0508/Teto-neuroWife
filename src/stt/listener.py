import torch
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000          # Whisper работает на 16 кГц
MODEL_SIZE = "small"         # tiny / base / small / medium / large-v3
DEVICE = "cpu"              # или "cpu"
COMPUTE_TYPE = "int8"        # int8 быстрее и легче

CHUNK = 512                  # Silero VAD требует РОВНО столько семплов при 16 кГц
VAD_THRESHOLD = 0.5          # выше — считаем речью
SILENCE_CHUNKS = 25          # ~0.8 сек тишины = конец фразы
MIN_SPEECH_CHUNKS = 8        # короче — считаем случайным шумом
GARBAGE = ["субтитр", "редактор", "корректор", "продолжение следует"]

def find_input_device(name_part: str) -> int:
    """Найти индекс устройства ЗАПИСИ по части названия."""
    for index, device in enumerate(sd.query_devices()):
        if name_part.lower() in device["name"].lower() and device["max_input_channels"] > 0:
            return index
    raise RuntimeError(f"Микрофон '{name_part}' не найден")


INPUT_DEVICE = find_input_device("MCHOSE")

class Listener:
    def __init__(self):
        self.vad, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad", model="silero_vad"
        )
        print(f"[stt] загружаю модель {MODEL_SIZE}...")
        self.model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        print("[stt] модель готова")

    def record(self, seconds: float = 5.0) -> np.ndarray:
        """Записать звук с микрофона."""
        audio = sd.rec(int(seconds * SAMPLE_RATE),samplerate=SAMPLE_RATE, channels=1, dtype="float32")
        sd.wait()          # дождаться конца записи
        return audio.flatten()   # (N,1) -> (N,) , Whisper ждёт одномерный массив

    def listen(self) -> np.ndarray | None:
        """Ждать речь, записать её целиком, вернуть när закончилась."""
        frames = []          # накопленный звук
        recording = False    # состояние: пишем или ждём
        silence = 0          # сколько подряд тихих кусочков

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",blocksize=CHUNK, device=INPUT_DEVICE) as stream:
            while True:
                chunk, _ = stream.read(CHUNK)
                chunk = chunk.flatten()

                
                prob = self.vad(torch.from_numpy(chunk), SAMPLE_RATE).item()
                if prob > 0.2:
                    print(f"  vad={prob:.2f}")
                is_speech = prob > VAD_THRESHOLD

                if is_speech:
                    if not recording:
                        recording = True
                        print("[stt] слушаю...")
                    silence = 0
                    frames.append(chunk)
                elif recording:
                    silence += 1
                    frames.append(chunk)          # тишину тоже пишем — она внутри фразы
                    if silence > SILENCE_CHUNKS:
                        break

        if len(frames) < MIN_SPEECH_CHUNKS:
            return None

        return np.concatenate(frames)

    def transcribe(self, audio: np.ndarray) -> str:
        """Распознать речь из массива."""
        segments, info = self.model.transcribe(audio, language="ru")
        text = " ".join(s.text for s in segments).strip()
        print(f"  [сырое] {text!r}") 
        low = text.lower()
        if any(g in low for g in GARBAGE):
            print("  [отсеяно как мусор]")
            return "" 
        return text
    
