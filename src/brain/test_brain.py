from brain import Brain

b = Brain()
for msg in ["Привет!", "У меня умерла собака...", "Ты такая милая!"]:
    print(msg, "->", b.respond(msg))