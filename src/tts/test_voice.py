import torch
import sounddevice as sd

LANGUAGE = "ru"
MODEL_ID = "v5_ru"        # попробуй также "v5_4_ru" — там вопросительная интонация
SPEAKER = "baya"
SAMPLE_RATE = 48000

print("[test] загружаю модель...")
model, _ = torch.hub.load(
    repo_or_dir="snakers4/silero-models",
    model="silero_tts",
    language=LANGUAGE,
    speaker=MODEL_ID,
)
model.to(torch.device("cpu"))
print(f"[test] голоса этой модели: {model.speakers}\n")


def play(audio):
    sd.play(audio.numpy(), SAMPLE_RATE)
    sd.wait()


def say_plain(text):
    print(f"[обычный] {text}")
    play(model.apply_tts(text=text, speaker=SPEAKER, sample_rate=SAMPLE_RATE))


def say_ssml(ssml):
    play(model.apply_tts(ssml_text=ssml, speaker=SPEAKER, sample_rate=SAMPLE_RATE))


# --- 1. Как звучит сейчас ---
say_plain("Ого, привет! Я так рада тебя видеть!")

# --- 2. То же самое, но с эмоцией ---
print("[ssml] с эмоцией")
say_ssml("""
<speak>
<prosody pitch="x-high" rate="fast">Ого, привет!</prosody>
<break time="300ms"/>
<prosody pitch="high">Я так рада тебя видеть!</prosody>
</speak>
""")

# --- 3. Пресеты эмоций: слушай и выбирай ---
PRESETS = {
    "радость":   ("x-high", "fast"),
    "спокойно":  ("medium", "medium"),
    "грусть":    ("low", "slow"),
    "удивление": ("x-high", "medium"),
    "смущение":  ("high", "slow"),
}

PHRASE = "Привет! Как твои дела сегодня?"

for name, (pitch, rate) in PRESETS.items():
    print(f"\n--- {name}: pitch={pitch}, rate={rate} ---")
    say_ssml(f'<speak><prosody pitch="{pitch}" rate="{rate}">{PHRASE}</prosody></speak>')