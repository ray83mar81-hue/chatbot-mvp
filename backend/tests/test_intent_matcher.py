from app.services.intent_matcher import _normalize, _similarity, FUZZY_THRESHOLD


def test_normalize_accents():
    assert _normalize("Horário") == "horario"
    assert _normalize("dirección") == "direccion"
    assert _normalize("¿Cuándo?") == "cuando"


def test_normalize_punctuation():
    assert _normalize("¡Hola!") == "hola"
    assert _normalize("precio?") == "precio"


def test_similarity_exact():
    assert _similarity("horario", "horario") == 1.0


def test_similarity_typo():
    sim = _similarity("horario", "horarioo")
    assert sim >= FUZZY_THRESHOLD


def test_similarity_plural():
    sim = _similarity("horario", "horarios")
    assert sim >= FUZZY_THRESHOLD


def test_similarity_verb_form():
    sim = _similarity("reserva", "reservar")
    assert sim >= FUZZY_THRESHOLD


def test_similarity_no_match():
    sim = _similarity("horario", "mesa")
    assert sim < FUZZY_THRESHOLD


def test_similarity_empty():
    assert _similarity("", "test") == 0.0
    assert _similarity("", "") == 0.0
