import torch
import numpy as np
import pyaudiowpatch as pyaudio
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
MODEL_SIZE = "medium"
DEVICE = "cuda"
COMPUTE_TYPE = "float16"

# какое устройство слушать (по части имени). "" = loopback дефолтных колонок.
LOOPBACK_MATCH = "CABLE In 16ch"

CHUNK = 512                  # Silero VAD требует РОВНО столько семплов при 16 кГц
READ_MS = 50

# --- пороги против болтливости ---
VAD_THRESHOLD = 0.6          # было 0.5; выше = меньше ложных срабатываний VAD на шум
RMS_GATE = 0.010             # тише этого куска = тишина/фон, в whisper не отдаём (лечит фантомы)
SILENCE_CHUNKS = 25          # ~0.8 сек тишины = конец фразы
MIN_SPEECH_CHUNKS = 15       # было 8; ~0.5с реальной речи минимум — режет короткие огрызки
MIN_TEXT_LEN = 3             # распознали короче — выкидываем ("хе", "а", "!")

GARBAGE = ["субтитр", "редактор", "корректор", "продолжение следует"]


class LoopbackListener:
    """Слушает кабель, куда выведен Discord (loopback)."""

    def __init__(self):
        self.vad, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad", model="silero_vad"
        )
        print(f"[ears] загружаю модель {MODEL_SIZE}...")
        self.model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        print("[ears] модель готова")

        self.pa = pyaudio.PyAudio()
        self.loop = self._find_loopback()
        self.src_rate = int(self.loop["defaultSampleRate"])
        self.channels = int(self.loop["maxInputChannels"])
        self.read_frames = int(self.src_rate * READ_MS / 1000)
        print(f"[ears] слушаю loopback: {self.loop['name']} "
              f"({self.src_rate} Гц, {self.channels} кан.)")

    def _find_loopback(self):
        if not LOOPBACK_MATCH:
            return self.pa.get_default_wasapi_loopback()
        for info in self.pa.get_loopback_device_info_generator():
            if LOOPBACK_MATCH.lower() in info["name"].lower():
                return info
        raise RuntimeError(
            f"[ears] loopback '{LOOPBACK_MATCH}' не найден. "
            f"Проверь: .venv\\Scripts\\python.exe -m pyaudiowpatch"
        )

    def _to_16k_mono(self, raw: bytes) -> np.ndarray:
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if self.channels > 1:
            a = a.reshape(-1, self.channels)
            take = min(2, self.channels)
            a = a[:, :take].mean(axis=1)
        if self.src_rate != SAMPLE_RATE and len(a) > 1:
            n_out = int(len(a) * SAMPLE_RATE / self.src_rate)
            a = np.interp(
                np.linspace(0, len(a), n_out, endpoint=False),
                np.arange(len(a)), a,
            ).astype(np.float32)
        return a

    def listen(self, is_speaking=None) -> np.ndarray | None:
        """Ждать речь и записать фразу. is_speaking() -> True => Тето заговорила,
        бросаем захват, чтобы не записать её собственный голос."""
        frames = []
        recording = False
        silence = 0
        buf = np.empty(0, dtype=np.float32)

        stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.src_rate,
            input=True,
            input_device_index=self.loop["index"],
            frames_per_buffer=self.read_frames,
        )
        try:
            while True:
                if is_speaking is not None and is_speaking():
                    return None

                raw = stream.read(self.read_frames, exception_on_overflow=False)
                buf = np.concatenate([buf, self._to_16k_mono(raw)])

                while len(buf) >= CHUNK:
                    chunk = buf[:CHUNK].copy()
                    buf = buf[CHUNK:]

                    prob = self.vad(torch.from_numpy(chunk), SAMPLE_RATE).item()
                    rms = float(np.sqrt(np.mean(chunk ** 2)))
                    # речь = и VAD уверен, И громкость выше порога (фон не проходит)
                    is_speech = prob > VAD_THRESHOLD and rms > RMS_GATE

                    if is_speech:
                        if not recording:
                            recording = True
                            print("[ears] слышу речь...")
                        silence = 0
                        frames.append(chunk)
                    elif recording:
                        silence += 1
                        frames.append(chunk)
                        if silence > SILENCE_CHUNKS:
                            if len(frames) < MIN_SPEECH_CHUNKS:
                                return None
                            return np.concatenate(frames)
        finally:
            stream.stop_stream()
            stream.close()

    def transcribe(self, audio: np.ndarray) -> str:
        segments, info = self.model.transcribe(audio, language="ru", vad_filter=True)
        text = " ".join(s.text for s in segments).strip()
        print(f"  [сырое] {text!r}")
        low = text.lower()
        if any(g in low for g in GARBAGE):
            print("  [отсеяно как мусор]")
            return ""
        if len(text.strip(" .,!?…-")) < MIN_TEXT_LEN:   # слишком короткий распознанный текст
            print("  [отсеяно как огрызок]")
            return ""
        return text