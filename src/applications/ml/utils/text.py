import textdistance


def similarity(value1, value2):
    value1 = value1.lower()
    value2 = value2.lower()

    return textdistance.damerau_levenshtein.normalized_similarity(value1, value2) +\
        textdistance.sorensen_dice.normalized_similarity(value1, value2) +\
        textdistance.lcsseq.normalized_similarity(value1, value2)
