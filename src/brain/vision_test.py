from vision import capture_screen
with open("test_shot.jpg", "wb") as f:
    f.write(capture_screen())