import torch
import sounddevice as sd

LANGUAGE = "ru"
MODEL_ID = "v5_ru"
SPEAKER = "baya"
SAMPLE_RATE = 48000


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

    def speak(self, text: str) -> None:
        """Синтезировать текст и проиграть через колонки."""
        if not text.strip():
            return

        audio = self.model.apply_tts(
            text=text, speaker=SPEAKER, sample_rate=SAMPLE_RATE
        )


        audio_np = audio.numpy()

        sd.play(audio_np, SAMPLE_RATE)
        sd.wait()
