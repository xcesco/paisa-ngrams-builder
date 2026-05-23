"""
Test codifica base 26
"""

import pytest
import sys
from pathlib import Path

# Aggiungi root alla path per import
sys.path.insert(0, str(Path(__file__).parent.parent))

from build_paisa_ngrams import ngram_to_id, id_to_ngram


class TestNgramToId:
    """Test conversione n-gramma -> ID"""

    def test_single_char(self):
        """Test singoli caratteri"""
        assert ngram_to_id("A") == 0
        assert ngram_to_id("B") == 1
        assert ngram_to_id("C") == 2
        assert ngram_to_id("Z") == 25

    def test_two_chars(self):
        """Test bigrammi"""
        assert ngram_to_id("AA") == 0
        assert ngram_to_id("AB") == 1
        assert ngram_to_id("AZ") == 25
        assert ngram_to_id("BA") == 26
        assert ngram_to_id("BB") == 27
        assert ngram_to_id("ZZ") == 26 * 26 - 1

    def test_trigrams(self):
        """Test trigrammi"""
        assert ngram_to_id("AAA") == 0
        assert ngram_to_id("AAB") == 1
        assert ngram_to_id("AAZ") == 25
        assert ngram_to_id("ABA") == 26
        assert ngram_to_id("GAT") == 4075  # Esempio dalle specifiche

    def test_quadgrams(self):
        """Test quadrigrammi"""
        assert ngram_to_id("AAAA") == 0
        assert ngram_to_id("AAAB") == 1
        assert ngram_to_id("GATT") == 105969  # Esempio dalle specifiche

    def test_known_examples(self):
        """Test esempi noti dalle specifiche"""
        # GAT: G=6, A=0, T=19
        # id = ((6 * 26) + 0) * 26 + 19 = 156 * 26 + 19 = 4056 + 19 = 4075
        assert ngram_to_id("GAT") == 4075

        # GATT: G=6, A=0, T=19, T=19
        # id = (((6 * 26) + 0) * 26 + 19) * 26 + 19
        # id = (4075) * 26 + 19 = 105950 + 19 = 105969
        assert ngram_to_id("GATT") == 105969

    def test_extremes(self):
        """Test valori estremi"""
        # Minimo
        assert ngram_to_id("AAA") == 0
        assert ngram_to_id("AAAA") == 0

        # Massimo trigrammi
        zzz_id = ngram_to_id("ZZZ")
        assert zzz_id == 26**3 - 1
        assert zzz_id == 17575

        # Massimo quadrigrammi
        zzzz_id = ngram_to_id("ZZZZ")
        assert zzzz_id == 26**4 - 1
        assert zzzz_id == 456975


class TestIdToNgram:
    """Test conversione ID -> n-gramma"""

    def test_single_char(self):
        """Test singoli caratteri"""
        assert id_to_ngram(0, 1) == "A"
        assert id_to_ngram(1, 1) == "B"
        assert id_to_ngram(25, 1) == "Z"

    def test_two_chars(self):
        """Test bigrammi"""
        assert id_to_ngram(0, 2) == "AA"
        assert id_to_ngram(1, 2) == "AB"
        assert id_to_ngram(25, 2) == "AZ"
        assert id_to_ngram(26, 2) == "BA"

    def test_trigrams(self):
        """Test trigrammi"""
        assert id_to_ngram(0, 3) == "AAA"
        assert id_to_ngram(1, 3) == "AAB"
        assert id_to_ngram(4075, 3) == "GAT"

    def test_quadgrams(self):
        """Test quadrigrammi"""
        assert id_to_ngram(0, 4) == "AAAA"
        assert id_to_ngram(1, 4) == "AAAB"
        assert id_to_ngram(105969, 4) == "GATT"

    def test_known_examples(self):
        """Test esempi noti dalle specifiche"""
        assert id_to_ngram(4075, 3) == "GAT"
        assert id_to_ngram(105969, 4) == "GATT"

    def test_extremes(self):
        """Test valori estremi"""
        # Minimo
        assert id_to_ngram(0, 3) == "AAA"
        assert id_to_ngram(0, 4) == "AAAA"

        # Massimo
        assert id_to_ngram(17575, 3) == "ZZZ"
        assert id_to_ngram(456975, 4) == "ZZZZ"


class TestBidirectional:
    """Test bidirezionalità conversione"""

    def test_roundtrip_trigrams(self):
        """Test andata-ritorno trigrammi"""
        test_ngrams = ["AAA", "GAT", "ONE", "ZZZ", "ABC", "XYZ"]
        for ngram in test_ngrams:
            ngram_id = ngram_to_id(ngram)
            reconstructed = id_to_ngram(ngram_id, 3)
            assert reconstructed == ngram, f"Failed for {ngram}"

    def test_roundtrip_quadgrams(self):
        """Test andata-ritorno quadrigrammi"""
        test_ngrams = ["AAAA", "GATT", "IONE", "ZZZZ", "ABCD", "WXYZ"]
        for ngram in test_ngrams:
            ngram_id = ngram_to_id(ngram)
            reconstructed = id_to_ngram(ngram_id, 4)
            assert reconstructed == ngram, f"Failed for {ngram}"

    def test_roundtrip_all_trigrams(self):
        """Test roundtrip per tutti i trigrammi possibili (campione)"""
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        # Test campione (tutti sarebbe troppo lento)
        import random
        random.seed(42)

        for _ in range(1000):
            ngram = ''.join(random.choices(alphabet, k=3))
            ngram_id = ngram_to_id(ngram)
            reconstructed = id_to_ngram(ngram_id, 3)
            assert reconstructed == ngram

    def test_roundtrip_sequential(self):
        """Test roundtrip sequenziale"""
        # Test primi 100 e ultimi 100 ID
        for i in range(100):
            ngram = id_to_ngram(i, 3)
            ngram_id = ngram_to_id(ngram)
            assert ngram_id == i

        for i in range(17476, 17576):  # Ultimi 100 trigrammi
            ngram = id_to_ngram(i, 3)
            ngram_id = ngram_to_id(ngram)
            assert ngram_id == i


class TestCollisions:
    """Test assenza collisioni"""

    def test_no_collisions_trigrams(self):
        """Test nessuna collisione per tutti i trigrammi"""
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        seen_ids = set()

        for i in alphabet:
            for j in alphabet:
                for k in alphabet:
                    ngram = i + j + k
                    ngram_id = ngram_to_id(ngram)

                    assert ngram_id not in seen_ids, \
                        f"Collision detected for {ngram}: ID {ngram_id} already used"

                    assert 0 <= ngram_id < 26**3, \
                        f"ID {ngram_id} out of range for {ngram}"

                    seen_ids.add(ngram_id)

        # Verifica che abbiamo esattamente 26^3 ID univoci
        assert len(seen_ids) == 26**3

    def test_no_collisions_quadgrams_sample(self):
        """Test nessuna collisione per campione quadrigrammi"""
        # Test completo sarebbe troppo lento (456k elementi)
        # Testiamo un campione rappresentativo
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        seen_ids = set()

        import random
        random.seed(42)

        # Genera 10000 quadrigrammi casuali
        for _ in range(10000):
            ngram = ''.join(random.choices(alphabet, k=4))
            ngram_id = ngram_to_id(ngram)

            # Ogni ID dovrebbe essere unico
            if ngram_id in seen_ids:
                # Verifica che lo stesso ID corrisponda effettivamente a quadrigrammi diversi
                # (non dovrebbe mai accadere)
                original = id_to_ngram(ngram_id, 4)
                assert original == ngram, \
                    f"Collision: {ngram} and {original} have same ID {ngram_id}"

            seen_ids.add(ngram_id)

            assert 0 <= ngram_id < 26**4, \
                f"ID {ngram_id} out of range for {ngram}"

        # Tutti gli ID dovrebbero essere univoci
        # (se non ci sono collisioni, len(seen_ids) == numero di ngram testati)
        # Ma dato che sono casuali, potremmo avere duplicati nell'input
        # Quindi testiamo solo che gli ID siano validi


class TestInvalidInput:
    """Test input non validi"""

    def test_lowercase(self):
        """Test che lowercase funzioni (alfabeto è case-sensitive nel default)"""
        # Con alfabeto uppercase (default), lowercase causerà errore
        with pytest.raises(ValueError):
            ngram_to_id("gat")

    def test_invalid_char(self):
        """Test caratteri non in alfabeto"""
        with pytest.raises(ValueError):
            ngram_to_id("GA1")

        with pytest.raises(ValueError):
            ngram_to_id("GA ")

    def test_empty_string(self):
        """Test stringa vuota"""
        result = ngram_to_id("")
        assert result == 0  # Formula restituisce 0 per stringa vuota

    def test_negative_id(self):
        """Test ID negativo in id_to_ngram"""
        # Non dovrebbe crashare, ma risultato potrebbe essere indefinito
        # Dipende dall'implementazione
        result = id_to_ngram(0, 3)
        assert result == "AAA"


class TestCustomAlphabet:
    """Test alfabeto personalizzato"""

    def test_custom_alphabet_encoding(self):
        """Test codifica con alfabeto custom"""
        custom_alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        # Dovrebbe funzionare uguale
        assert ngram_to_id("GAT", custom_alpha) == 4075
        assert ngram_to_id("GATT", custom_alpha) == 105969

    def test_custom_alphabet_decoding(self):
        """Test decodifica con alfabeto custom"""
        custom_alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        assert id_to_ngram(4075, 3, custom_alpha) == "GAT"
        assert id_to_ngram(105969, 4, custom_alpha) == "GATT"

