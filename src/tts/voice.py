import torch
import torch.serialization

# Патч torch.load для fairseq-моделей RVC (сохранены в старом формате)
try:
    from fairseq.data.dictionary import Dictionary
    torch.serialization.add_safe_globals([Dictionary])
except Exception as e:
    print(f"[voice] safe_globals: {e}")

import sounddevice as sd
import html
from infer_rvc_python import BaseLoader

LANGUAGE = "ru"
MODEL_ID = "v5_ru"
SPEAKER = "baya"
SAMPLE_RATE = 48000

RVC_MODEL = r"C:\rvc-models\teto\KasaneTetotalkcvlc1.5_215e_7740s.pth"
RVC_INDEX = r"C:\rvc-models\teto\KasaneTetotalkcvlc1.5.index"

OUTPUT_DEVICE = 16      # в кабель -> VTube Studio липсинк

PROSODY = {
    "joy":         ("high", "fast"),
    "embarrassed": ("medium", "slow"),
    # остальные эмоции -> None (обычный голос)
}


class Voice:
    def __init__(self):
        print("[voice] загружаю Silero...")
        self.model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-models", model="silero_tts",
            language=LANGUAGE, speaker=MODEL_ID,
        )
        self.model.to(torch.device("cpu"))

        print("[voice] загружаю RVC Тето...")
        self.rvc = BaseLoader(only_cpu=False)
        self.rvc.apply_conf(
            tag="teto",
            file_model=RVC_MODEL,
            file_index=RVC_INDEX,
            pitch_algo="rmvpe+",
            pitch_lvl=-2,
            index_influence=0.75,
        )
        print("[voice] голос готов")

    def speak(self, text: str, emotion: str = "neutral") -> None:
        """Silero синтезирует речь -> RVC красит в голос Тето -> играем в кабель."""
        if not text.strip():
            return

        # 1. Silero: русская речь в numpy-массив
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

        # 2. RVC: перекраска тембра в Тето (массив -> массив, без файлов)
        result_array, sr = self.rvc.generate_from_cache(
            audio_data=(audio.numpy(), SAMPLE_RATE), tag="teto"
        )

        # 3. Проигрывание в кабель на РОДНОЙ частоте RVC (32000 для модели Тето).
        #    Никакого ресемпла — играем ровно с тем sr, что вернул RVC.
        sd.play(result_array, samplerate=sr, device=OUTPUT_DEVICE)
        sd.wait()