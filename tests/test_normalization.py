"""
Test normalizzazione testo
"""

import pytest
import sys
from pathlib import Path

# Aggiungi root alla path per import
sys.path.insert(0, str(Path(__file__).parent.parent))

from build_paisa_ngrams import (
    strip_accents,
    remove_tags,
    normalize_to_words
)


class TestStripAccents:
    """Test rimozione accenti"""

    def test_basic_accents(self):
        """Test accenti base italiani"""
        assert strip_accents("perché") == "perche"
        assert strip_accents("città") == "citta"
        assert strip_accents("può") == "puo"
        assert strip_accents("più") == "piu"
        assert strip_accents("così") == "cosi"

    def test_all_accent_variants(self):
        """Test tutte le varianti di accenti"""
        # A variants
        assert strip_accents("à á â ä ã å") == "a a a a a a"
        # E variants
        assert strip_accents("è é ê ë") == "e e e e"
        # I variants
        assert strip_accents("ì í î ï") == "i i i i"
        # O variants
        assert strip_accents("ò ó ô ö õ") == "o o o o o"
        # U variants
        assert strip_accents("ù ú û ü") == "u u u u"
        # C cedilla
        assert strip_accents("ç") == "c"

    def test_mixed_text(self):
        """Test testo misto con e senza accenti"""
        assert strip_accents("università") == "universita"
        assert strip_accents("È l'università più bella") == "E l'universita piu bella"

    def test_no_accents(self):
        """Test testo senza accenti rimane invariato"""
        assert strip_accents("gatto nero") == "gatto nero"
        assert strip_accents("ABCDEFGHIJKLMNOPQRSTUVWXYZ") == "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class TestRemoveTags:
    """Test rimozione tag XML/HTML"""

    def test_simple_tag(self):
        """Test tag semplici"""
        assert remove_tags("<b>ciao</b>") == "ciao"
        assert remove_tags("<text>contenuto</text>") == "contenuto"

    def test_tag_with_attributes(self):
        """Test tag con attributi"""
        assert remove_tags('<text id="123">contenuto</text>') == "contenuto"
        assert remove_tags('<a href="http://example.com">link</a>') == "link"

    def test_multiple_tags(self):
        """Test multipli tag"""
        assert remove_tags("<b>grassetto</b> e <i>corsivo</i>") == "grassetto e corsivo"

    def test_nested_tags(self):
        """Test tag annidati"""
        assert remove_tags("<p><b>testo</b></p>") == "testo"

    def test_no_tags(self):
        """Test testo senza tag"""
        assert remove_tags("testo semplice") == "testo semplice"


class TestNormalizeToWords:
    """Test normalizzazione completa in parole"""

    def test_basic_normalization(self):
        """Test normalizzazione base"""
        assert normalize_to_words("Il gatto nero") == ["IL", "GATTO", "NERO"]
        assert normalize_to_words("ciao mondo") == ["CIAO", "MONDO"]

    def test_accents_removal(self):
        """Test rimozione accenti in normalizzazione"""
        assert normalize_to_words("perché") == ["PERCHE"]
        assert normalize_to_words("città") == ["CITTA"]
        assert normalize_to_words("può più così") == ["PUO", "PIU", "COSI"]
        assert normalize_to_words("università") == ["UNIVERSITA"]

    def test_apostrophes(self):
        """Test gestione apostrofi"""
        assert normalize_to_words("E' fondamentale") == ["E", "FONDAMENTALE"]
        assert normalize_to_words("quest'inspiegabile") == ["QUEST", "INSPIEGABILE"]
        assert normalize_to_words("l'università") == ["L", "UNIVERSITA"]
        assert normalize_to_words("d'Italia") == ["D", "ITALIA"]

    def test_numbers_and_symbols(self):
        """Test numeri e simboli come delimitatori"""
        assert normalize_to_words("larghezza 1/8\"") == ["LARGHEZZA"]
        assert normalize_to_words("test 123 parola") == ["TEST", "PAROLA"]
        assert normalize_to_words("a-b-c") == ["A", "B", "C"]

    def test_punctuation(self):
        """Test punteggiatura"""
        assert normalize_to_words("Ciao, mondo!") == ["CIAO", "MONDO"]
        assert normalize_to_words("Primo. Secondo? Terzo!") == ["PRIMO", "SECONDO", "TERZO"]

    def test_tags_removal(self):
        """Test rimozione tag in normalizzazione"""
        assert normalize_to_words("<b>ciao</b>") == ["CIAO"]
        assert normalize_to_words("<text>Roma</text>") == ["ROMA"]
        assert normalize_to_words("<b>Roma</b> è bella") == ["ROMA", "E", "BELLA"]

    def test_empty_input(self):
        """Test input vuoto"""
        assert normalize_to_words("") == []
        assert normalize_to_words("   ") == []
        assert normalize_to_words("123 456") == []

    def test_only_symbols(self):
        """Test solo simboli/numeri"""
        assert normalize_to_words("!@#$%^&*()") == []
        assert normalize_to_words("12345") == []

    def test_mixed_case(self):
        """Test conversione maiuscolo"""
        assert normalize_to_words("CaSo MiStO") == ["CASO", "MISTO"]
        assert normalize_to_words("TUTTO MAIUSCOLO") == ["TUTTO", "MAIUSCOLO"]
        assert normalize_to_words("tutto minuscolo") == ["TUTTO", "MINUSCOLO"]

    def test_complex_example(self):
        """Test esempio complesso dalle specifiche"""
        # Dalla fixture
        text = "Perché la città è più bella?"
        expected = ["PERCHE", "LA", "CITTA", "E", "PIU", "BELLA"]
        assert normalize_to_words(text) == expected

    def test_multiline(self):
        """Test testo multilinea"""
        text = "Prima riga\nSeconda riga"
        assert normalize_to_words(text) == ["PRIMA", "RIGA", "SECONDA", "RIGA"]


class TestEdgeCases:
    """Test casi edge"""

    def test_unicode_characters(self):
        """Test caratteri unicode vari"""
        # Caratteri speciali dovrebbero essere rimossi
        result = normalize_to_words("test © ® ™ test")
        assert "TEST" in result

    def test_very_long_word(self):
        """Test parola molto lunga"""
        long_word = "A" * 1000
        result = normalize_to_words(long_word)
        assert len(result) == 1
        assert result[0] == long_word

    def test_url_like(self):
        """Test URL-like strings"""
        result = normalize_to_words("http://www.example.com")
        assert result == ["HTTP", "WWW", "EXAMPLE", "COM"]

    def test_email_like(self):
        """Test email-like strings"""
        result = normalize_to_words("test@example.com")
        assert "TEST" in result
        assert "EXAMPLE" in result
        assert "COM" in result

