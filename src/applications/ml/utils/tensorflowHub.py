import tensorflow_hub as hub


def load():
    try:
        embed = hub.load("https://tfhub.dev/google/universal-sentence-encoder/4")
        return embed
    except Exception as exc:
        return None


# embed = load()
