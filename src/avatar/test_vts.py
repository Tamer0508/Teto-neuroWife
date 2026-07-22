import asyncio
from vts import VTS

async def main():
    vts = VTS()
    await vts.connect()

    for emotion in ["joy", "sad", "smug", "embarrassed", "confused", "neutral"]:
        print(emotion)
        await vts.set_emotion(emotion)
        await asyncio.sleep(2)

asyncio.run(main())