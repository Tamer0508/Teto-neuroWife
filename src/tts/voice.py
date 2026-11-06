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

# Устройство вывода ищем по ИМЕНИ (индексы съезжают при смене устройств).
# DirectSound спокойно принимает родную частоту RVC и сам ресемплит в кабель —
# поэтому НИКАКОГО soxr/пересчёта в коде: играем ровно то, что отдал RVC.
OUTPUT_DEVICE_NAME = "CABLE Input"
OUTPUT_HOSTAPI = "DirectSound"

PROSODY = {
    "joy":         ("high", "fast"),
    "embarrassed": ("medium", "slow"),
    # остальные эмоции -> None (обычный голос)
}


def find_output_device(name_part: str, hostapi_part: str | None = None) -> int:
    """Найти устройство ВЫВОДА по части имени. Если задан hostapi_part
    (например 'DirectSound') — предпочесть его, иначе взять любое совпадение."""
    target_api = None
    if hostapi_part:
        for i, api in enumerate(sd.query_hostapis()):
            if hostapi_part.lower() in api["name"].lower():
                target_api = i
                break

    any_match = None
    api_match = None
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_output_channels"] > 0 and name_part.lower() in dev["name"].lower():
            if any_match is None:
                any_match = idx
            if target_api is not None and dev["hostapi"] == target_api:
                api_match = idx
                break

    chosen = api_match if api_match is not None else any_match
    if chosen is None:
        raise RuntimeError(f"[voice] устройство вывода '{name_part}' не найдено")
    return chosen


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

        self.output_device = find_output_device(OUTPUT_DEVICE_NAME, OUTPUT_HOSTAPI)
        dev = sd.query_devices(self.output_device)
        api = sd.query_hostapis(dev["hostapi"])["name"]
        print(f"[voice] вывод -> [{self.output_device}] {dev['name']} ({api})")
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
        print(f"[voice] RVC отдал sr={sr}")   # диагностика частоты — скажи, что печатает

        # 3. Проигрывание на РОДНОЙ частоте RVC, без ресемпла.
        #    DirectSound сам приведёт к формату кабеля.
        sd.play(result_array, samplerate=sr, device=self.output_device)
        sd.wait()