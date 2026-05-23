"""
Test estrazione n-grammi
"""

import pytest
import sys
from pathlib import Path
from collections import Counter

# Aggiungi root alla path per import
sys.path.insert(0, str(Path(__file__).parent.parent))

from build_paisa_ngrams import (
    iter_ngrams_from_word,
    iter_ngrams_from_text,
    split_line_into_segments,
    update_inword_counts,
    update_continuous_counts,
    ngram_to_id
)


class TestIterNgramsFromWord:
    """Test estrazione n-grammi da singola parola"""

    def test_trigrams_basic(self):
        """Test trigrammi base"""
        result = list(iter_ngrams_from_word("GATTO", 3))
        assert result == ["GAT", "ATT", "TTO"]

    def test_quadgrams_basic(self):
        """Test quadrigrammi base"""
        result = list(iter_ngrams_from_word("GATTO", 4))
        assert result == ["GATT", "ATTO"]

    def test_short_word(self):
        """Test parola corta"""
        # Parola più corta di n -> nessun n-gramma
        assert list(iter_ngrams_from_word("GA", 3)) == []
        assert list(iter_ngrams_from_word("GAT", 4)) == []

    def test_exact_length(self):
        """Test parola lunghezza esatta n"""
        assert list(iter_ngrams_from_word("GAT", 3)) == ["GAT"]
        assert list(iter_ngrams_from_word("GATT", 4)) == ["GATT"]

    def test_long_word(self):
        """Test parola lunga"""
        result = list(iter_ngrams_from_word("UNIVERSITA", 3))
        expected_count = len("UNIVERSITA") - 3 + 1
        assert len(result) == expected_count
        assert result[0] == "UNI"
        assert result[-1] == "ITA"

    def test_overlapping(self):
        """Test sovrapposizione corretta"""
        result = list(iter_ngrams_from_word("ABCD", 3))
        assert result == ["ABC", "BCD"]
        # Verifica sovrapposizione: BC è condiviso


class TestIterNgramsFromText:
    """Test estrazione n-grammi da testo continuo"""

    def test_continuous_trigrams(self):
        """Test trigrammi continuous"""
        result = list(iter_ngrams_from_text("GATTONERO", 3))
        assert "GAT" in result
        assert "ATT" in result
        assert "TTO" in result
        assert "TON" in result  # Cross-word
        assert "ONE" in result  # Cross-word
        assert "NER" in result
        assert "ERO" in result

    def test_continuous_quadgrams(self):
        """Test quadrigrammi continuous"""
        result = list(iter_ngrams_from_text("GATTONERO", 4))
        assert "GATT" in result
        assert "ATTO" in result
        assert "TTON" in result  # Cross-word
        assert "TONE" in result  # Cross-word
        assert "ONER" in result  # Cross-word
        assert "NERO" in result


class TestSplitLineIntoSegments:
    """Test split linea in segmenti"""

    def test_sentence_mode_basic(self):
        """Test modalità sentence base"""
        segments = split_line_into_segments(
            "Il gatto nero. Dorme sul divano.",
            mode='sentence'
        )

        # Dovrebbero esserci 2 segmenti (split sul punto)
        assert len(segments) == 2

        # Primo segmento
        assert segments[0] == ["IL", "GATTO", "NERO"]

        # Secondo segmento
        assert segments[1] == ["DORME", "SUL", "DIVANO"]

    def test_sentence_mode_comma(self):
        """Test sentence mode con virgola"""
        segments = split_line_into_segments(
            "Gatto nero, molto bello",
            mode='sentence'
        )

        assert len(segments) == 2
        assert segments[0] == ["GATTO", "NERO"]
        assert segments[1] == ["MOLTO", "BELLO"]

    def test_sentence_mode_multiple_delimiters(self):
        """Test sentence mode con multipli delimitatori"""
        segments = split_line_into_segments(
            "Primo! Secondo? Terzo.",
            mode='sentence'
        )

        assert len(segments) == 3

    def test_strict_mode(self):
        """Test modalità strict"""
        segments = split_line_into_segments(
            "Il gatto nero",
            mode='strict'
        )

        # In strict, ogni parola è isolata
        assert len(segments) == 3
        assert segments[0] == ["IL"]
        assert segments[1] == ["GATTO"]
        assert segments[2] == ["NERO"]

    def test_line_mode(self):
        """Test modalità line"""
        segments = split_line_into_segments(
            "Il gatto nero. Dorme.",
            mode='line'
        )

        # Tutta la riga in un segmento
        assert len(segments) == 1
        # Il punto viene rimosso dalla normalizzazione
        assert "IL" in segments[0]
        assert "GATTO" in segments[0]
        assert "NERO" in segments[0]
        assert "DORME" in segments[0]

    def test_document_mode(self):
        """Test modalità document"""
        segments = split_line_into_segments(
            "Il gatto nero. Dorme.",
            mode='document'
        )

        # Come line mode
        assert len(segments) == 1

    def test_empty_line(self):
        """Test riga vuota"""
        segments = split_line_into_segments("", mode='sentence')
        assert segments == []

    def test_only_punctuation(self):
        """Test solo punteggiatura"""
        segments = split_line_into_segments("... !!! ???", mode='sentence')
        assert segments == []

    def test_numbers_as_delimiters(self):
        """Test numeri come delimitatori in sentence mode"""
        segments = split_line_into_segments(
            "larghezza 1/8 pollici",
            mode='sentence'
        )

        # Il numero dovrebbe separare i segmenti
        # Almeno 2 segmenti
        assert len(segments) >= 1

        # Verifica che LARGHEZZA sia in un segmento
        found = False
        for seg in segments:
            if "LARGHEZZA" in seg:
                found = True
        assert found


class TestUpdateInwordCounts:
    """Test aggiornamento contatori inword"""

    def test_simple_update(self):
        """Test aggiornamento semplice"""
        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        words = ["GATTO", "NERO"]
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        num_words, num_chars = update_inword_counts(
            words, counts, 3, 4, alphabet
        )

        assert num_words == 2
        assert num_chars == len("GATTO") + len("NERO")

        # Verifica conteggi trigrammi
        gat_id = ngram_to_id("GAT", alphabet)
        assert counts['inword'][3][gat_id] == 1

        att_id = ngram_to_id("ATT", alphabet)
        assert counts['inword'][3][att_id] == 1

        # Verifica conteggi quadrigrammi
        gatt_id = ngram_to_id("GATT", alphabet)
        assert counts['inword'][4][gatt_id] == 1

    def test_no_cross_word(self):
        """Test che inword NON generi cross-word n-grams"""
        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        words = ["GATTO", "NERO"]
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        update_inword_counts(words, counts, 3, 4, alphabet)

        # TON, ONE, RONE non dovrebbero esistere (sono cross-word)
        ton_id = ngram_to_id("TON", alphabet)
        one_id = ngram_to_id("ONE", alphabet)

        assert counts['inword'][3][ton_id] == 0
        assert counts['inword'][3][one_id] == 0

    def test_repeated_ngrams(self):
        """Test n-grammi ripetuti"""
        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        # ATT appare in entrambe le parole
        words = ["GATTO", "ATTO"]
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        update_inword_counts(words, counts, 3, 4, alphabet)

        att_id = ngram_to_id("ATT", alphabet)
        assert counts['inword'][3][att_id] == 2


class TestUpdateContinuousCounts:
    """Test aggiornamento contatori continuous"""

    def test_simple_update(self):
        """Test aggiornamento semplice"""
        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        segments = [["IL", "GATTO", "NERO"]]
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        num_chars = update_continuous_counts(segments, counts, 3, 4, alphabet)

        assert num_chars == len("ILGATTONERO")

        # Verifica cross-word n-grams
        ton_id = ngram_to_id("TON", alphabet)
        assert counts['continuous'][3][ton_id] == 1

        one_id = ngram_to_id("ONE", alphabet)
        assert counts['continuous'][3][one_id] == 1

    def test_multiple_segments(self):
        """Test segmenti multipli"""
        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        # Due segmenti separati
        segments = [
            ["IL", "GATTO"],
            ["NERO"]
        ]
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        update_continuous_counts(segments, counts, 3, 4, alphabet)

        # TON non dovrebbe esistere (attraverserebbe segmenti)
        ton_id = ngram_to_id("TON", alphabet)
        assert counts['continuous'][3][ton_id] == 0

        # Ma ILGATTO e NERO dovrebbero generare i loro n-grammi
        gat_id = ngram_to_id("GAT", alphabet)
        assert counts['continuous'][3][gat_id] == 1

    def test_cross_word_ngrams(self):
        """Test generazione cross-word n-grams"""
        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        segments = [["GATTO", "NERO"]]
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        update_continuous_counts(segments, counts, 3, 4, alphabet)

        # Cross-word trigrams
        assert counts['continuous'][3][ngram_to_id("TON", alphabet)] == 1
        assert counts['continuous'][3][ngram_to_id("ONE", alphabet)] == 1

        # Cross-word quadgrams
        assert counts['continuous'][4][ngram_to_id("TONE", alphabet)] == 1
        assert counts['continuous'][4][ngram_to_id("ONER", alphabet)] == 1


class TestInwordVsContinuous:
    """Test differenza tra inword e continuous"""

    def test_difference(self):
        """Test che inword e continuous diano risultati diversi"""
        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        words = ["GATTO", "NERO"]
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        # Aggiorna inword
        update_inword_counts(words, counts, 3, 4, alphabet)

        # Aggiorna continuous
        segments = [words]  # Un segmento con entrambe le parole
        update_continuous_counts(segments, counts, 3, 4, alphabet)

        # TON esiste in continuous ma non in inword
        ton_id = ngram_to_id("TON", alphabet)
        assert counts['continuous'][3][ton_id] == 1
        assert counts['inword'][3][ton_id] == 0

        # GAT esiste in entrambi
        gat_id = ngram_to_id("GAT", alphabet)
        assert counts['continuous'][3][gat_id] == 1
        assert counts['inword'][3][gat_id] == 1

        # Ma continuous ha più n-grammi totali
        assert sum(counts['continuous'][3].values()) > sum(counts['inword'][3].values())


class TestEdgeCases:
    """Test casi edge"""

    def test_single_letter_word(self):
        """Test parola singola lettera"""
        result = list(iter_ngrams_from_word("A", 3))
        assert result == []

    def test_two_letter_word(self):
        """Test parola due lettere"""
        result = list(iter_ngrams_from_word("AB", 3))
        assert result == []

        result = list(iter_ngrams_from_word("AB", 4))
        assert result == []

    def test_empty_segments(self):
        """Test segmenti vuoti"""
        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        segments = [[], ["GATTO"], []]
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        # Non dovrebbe crashare
        num_chars = update_continuous_counts(segments, counts, 3, 4, alphabet)
        assert num_chars == len("GATTO")

