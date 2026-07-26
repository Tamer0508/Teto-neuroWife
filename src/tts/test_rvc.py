import time
import torch
import torch.serialization
import soundfile as sf
from infer_rvc_python import BaseLoader

# Разрешаем fairseq-объекты при загрузке (RVC сохранён в старом формате)
try:
    from fairseq.data.dictionary import Dictionary
    torch.serialization.add_safe_globals([Dictionary])
except Exception as e:
    print(f"[patch] не удалось добавить safe_globals: {e}")

# --- Загрузка RVC-модели Тето ---
print("[rvc] инициализация...")
converter = BaseLoader(only_cpu=False)

print("[rvc] загружаю модель Тето...")
converter.apply_conf(
    tag="teto",
    file_model=r"C:\rvc-models\teto\KasaneTetotalkcvlc1.5_215e_7740s.pth",
    file_index=r"C:\rvc-models\teto\KasaneTetotalkcvlc1.5.index",
    pitch_algo="rmvpe+",
    pitch_lvl=-2,
    index_influence=0.75,
)
print("[rvc] модель загружена!")

# --- Генерим тестовую фразу через Silero ---
print("[silero] генерю тестовую фразу...")
model, _ = torch.hub.load("snakers4/silero-models", "silero_tts",
                          language="ru", speaker="v5_ru")
model.to(torch.device("cpu"))
audio = model.apply_tts(text="Привет, это проверка голоса Тето через RVC конверсию!",
                        speaker="baya", sample_rate=48000)
sf.write("test_input.wav", audio.numpy(), 48000)
print("[silero] готово")

# --- Конверсия через RVC с замером ---
print("[rvc] конвертирую...")
t0 = time.perf_counter()
result_array, sample_rate = converter.generate_from_cache(
    audio_data="test_input.wav", tag="teto"
)
print(f"[rvc] готово за {time.perf_counter() - t0:.2f}s")

sf.write("test_teto.wav", result_array, sample_rate)
print("[rvc] сохранено в test_teto.wav — послушай!")

# вторая конверсия — модель уже в памяти, замерим чистое время
import time
t0 = time.perf_counter()
result_array, sample_rate = converter.generate_from_cache(
    audio_data="test_input.wav", tag="teto"
)
print(f"[rvc] ВТОРАЯ конверсия за {time.perf_counter() - t0:.2f}s")