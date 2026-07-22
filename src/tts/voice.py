import torch
import sounddevice as sd
import html

LANGUAGE = "ru"
MODEL_ID = "v5_ru"
SPEAKER = "baya"
SAMPLE_RATE = 48000
PROSODY = {
    "joy":         ("high", "fast"),
    "neutral":     None,                  # без разметки, обычный голос
    "love":        ("high", "slow"),
    "embarrassed": ("medium", "slow"),
    "smug":        ("medium", "slow"),
    "sad":         ("medium", "slow"),
    "confused":    ("medium", "slow"),
}
def find_device(name_part: str) -> int:
    """Найти индекс устройства ВЫВОДА по части названия."""
    for index, device in enumerate(sd.query_devices()):
        if name_part.lower() in device["name"].lower() and device["max_output_channels"] > 0:
            return index
    raise RuntimeError(f"Устройство '{name_part}' не найдено")

OUTPUT_DEVICE = find_device("CABLE Input")


class Voice:
    def __init__(self):
        print("[voice] загружаю модель...")

        self.model, _ = torch.hub.load(
              repo_or_dir="snakers4/silero-models",
              model="silero_tts",
              language=LANGUAGE,
              speaker=MODEL_ID,
          )


        self.model.to(torch.device("cpu"))

        print("[voice] модель готова")
    
    def speak(self, text: str, emotion: str = "neutral") -> None:
        """Синтезировать текст и проиграть через колонки."""
        if not text.strip():
            return
        
        preset = PROSODY.get(emotion)
        if preset is None:
            audio = self.model.apply_tts(
                text=text, speaker=SPEAKER, sample_rate=SAMPLE_RATE
            )
        else:
            pitch, rate = preset     
            safe = html.escape(text)
            ssml = f'<speak><prosody pitch="{pitch}" rate="{rate}">{safe}</prosody></speak>'

            audio = self.model.apply_tts(
                ssml_text=ssml, speaker=SPEAKER, sample_rate=SAMPLE_RATE
            )
        sd.play(audio.numpy(), SAMPLE_RATE, device=OUTPUT_DEVICE)
        sd.wait()
