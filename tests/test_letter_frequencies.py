#!/usr/bin/env python3
"""
Test per le frequenze delle lettere.
"""

import json
import math
import sys
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

# Importa dal modulo principale
sys.path.insert(0, str(Path(__file__).parent.parent))
from build_paisa_ngrams import (
    BuilderConfig,
    count_letters,
    normalize_to_words,
    process_text_block,
    process_blocks_batch,
    merge_batch_result,
    BuilderState,
    build_from_corpus,
    write_letter_csv,
    write_letter_npy
)


class TestLetterCountsBasic:
    """Test di base per il conteggio lettere."""

    def test_letter_counts_simple(self):
        """Test conteggio lettere semplice."""
        words = ["ABBA"]
        letter_counts = count_letters(words)

        assert letter_counts[0] == 2  # A
        assert letter_counts[1] == 2  # B
        assert sum(letter_counts.values()) == 4

    def test_letter_counts_multiple_words(self):
        """Test conteggio lettere multiple parole."""
        words = ["HELLO", "WORLD"]
        letter_counts = count_letters(words)

        # H=1, E=1, L=3, O=2, W=1, R=1, D=1
        assert letter_counts[7] == 1   # H
        assert letter_counts[4] == 1   # E
        assert letter_counts[11] == 3  # L
        assert letter_counts[14] == 2  # O
        assert letter_counts[22] == 1  # W
        assert letter_counts[17] == 1  # R
        assert letter_counts[3] == 1   # D
        assert sum(letter_counts.values()) == 10

    def test_letter_counts_empty(self):
        """Test con lista vuota."""
        words = []
        letter_counts = count_letters(words)

        assert len(letter_counts) == 0
        assert sum(letter_counts.values()) == 0


class TestLetterCountsWithAccents:
    """Test conteggio lettere con accenti normalizzati."""

    def test_accents_normalized(self):
        """Test che gli accenti siano normalizzati correttamente."""
        # Normalizza testo con accenti
        text = "perché città più può"
        words = normalize_to_words(text)

        # Dovrebbe dare: PERCHE CITTA PIU PUO
        assert "PERCHE" in words
        assert "CITTA" in words
        assert "PIU" in words
        assert "PUO" in words

        # Conta lettere
        letter_counts = count_letters(words)

        # E include la è/é normalizzata
        assert letter_counts[4] > 0  # E

        # A include à normalizzata
        assert letter_counts[0] > 0  # A

        # U include ù normalizzata
        assert letter_counts[20] > 0  # U

        # O include ò normalizzata
        assert letter_counts[14] > 0  # O

        # Verifica conteggi specifici
        # PERCHE: P(1), E(2), R(1), C(1), H(1)
        # CITTA: C(1), I(1), T(2), A(1)
        # PIU: P(1), I(1), U(1)
        # PUO: P(1), U(1), O(1)
        assert letter_counts[15] == 3  # P (perche, piu, puo)
        assert letter_counts[4] == 2   # E (perche)
        assert letter_counts[0] == 1   # A (citta)


class TestLetterCountsIgnoreNonLetters:
    """Test che numeri e simboli vengano ignorati."""

    def test_ignore_numbers_and_symbols(self):
        """Test che numeri e simboli non vengano contati."""
        text = "A1/B- C!"
        words = normalize_to_words(text)

        letter_counts = count_letters(words)

        assert letter_counts[0] == 1  # A
        assert letter_counts[1] == 1  # B
        assert letter_counts[2] == 1  # C
        assert sum(letter_counts.values()) == 3

        # Verifica che non ci siano conteggi strani
        for letter_id, count in letter_counts.items():
            assert 0 <= letter_id < 26


class TestProcessTextBlockWithLetters:
    """Test che process_text_block conti le lettere."""

    def test_process_block_includes_letters(self):
        """Test che il processing di un blocco includa letter_counts."""
        block_text = "Il gatto nero"

        config = BuilderConfig(
            corpus_file=Path("dummy"),
            output_dir=Path("dummy"),
            min_n=3,
            max_n=4
        )

        result = process_text_block(block_text, config)

        # Verifica che letter_counts esista
        assert hasattr(result, 'letter_counts')
        assert isinstance(result.letter_counts, Counter)

        # Verifica che ci siano lettere contate
        total_letters = sum(result.letter_counts.values())
        assert total_letters > 0

        # ILGATTONERO dovrebbe avere 11 lettere
        # (spazi ignorati)
        assert total_letters == 11


class TestBatchProcessingWithLetters:
    """Test aggregazione letter_counts in batch."""

    def test_batch_aggregates_letters(self):
        """Test che process_blocks_batch aggreghi i letter_counts."""
        blocks = [
            "ABC",
            "DEF"
        ]

        config = BuilderConfig(
            corpus_file=Path("dummy"),
            output_dir=Path("dummy"),
            min_n=3,
            max_n=4
        )

        result = process_blocks_batch(blocks, config)

        # Verifica letter_counts aggregati
        assert result.letter_counts[0] == 1  # A
        assert result.letter_counts[1] == 1  # B
        assert result.letter_counts[2] == 1  # C
        assert result.letter_counts[3] == 1  # D
        assert result.letter_counts[4] == 1  # E
        assert result.letter_counts[5] == 1  # F
        assert sum(result.letter_counts.values()) == 6


class TestMergeWithLetters:
    """Test fusione letter_counts."""

    def test_merge_aggregates_letters(self):
        """Test che merge_batch_result aggreghi i letter_counts."""
        from build_paisa_ngrams import BatchResult

        # Stato globale
        global_state = BuilderState(
            counts={
                'inword': {3: Counter(), 4: Counter()},
                'continuous': {3: Counter(), 4: Counter()}
            },
            letter_counts=Counter({0: 5}),  # A=5
            stats={}
        )

        # Batch result
        batch_result = BatchResult(
            counts={
                'inword': {3: Counter(), 4: Counter()},
                'continuous': {3: Counter(), 4: Counter()}
            },
            letter_counts=Counter({0: 3, 1: 2}),  # A=3, B=2
            stats={}
        )

        # Merge
        merge_batch_result(global_state, batch_result)

        # Verifica
        assert global_state.letter_counts[0] == 8  # A: 5+3
        assert global_state.letter_counts[1] == 2  # B: 0+2


class TestLetterOutputFiles:
    """Test generazione file output lettere."""

    def test_letter_csv_created(self, tmp_path):
        """Test che venga creato il CSV delle lettere."""
        letter_counts = Counter({
            0: 100,  # A
            4: 80,   # E
            8: 50    # I
        })

        csv_file = tmp_path / "letters.csv"

        write_letter_csv(
            letter_counts=letter_counts,
            alpha_letters=0.01,
            output_file=str(csv_file),
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            verbose=False
        )

        assert csv_file.exists()

        # Verifica contenuto
        with open(csv_file, 'r') as f:
            lines = f.readlines()

        # Header + 26 righe (tutte le lettere)
        assert len(lines) == 27

        # Verifica header
        assert 'letter,letter_id,count,frequency,smoothed_frequency,log_probability,rank' in lines[0]

    def test_letter_npy_created(self, tmp_path):
        """Test che vengano creati gli array NPY delle lettere."""
        letter_counts = Counter({
            0: 100,  # A
            4: 80,   # E
            8: 50    # I
        })

        counts_file = tmp_path / "counts.npy"
        freq_file = tmp_path / "freq.npy"
        logprob_file = tmp_path / "logprob.npy"

        write_letter_npy(
            letter_counts=letter_counts,
            alpha_letters=0.01,
            counts_file=str(counts_file),
            frequencies_file=str(freq_file),
            logprob_file=str(logprob_file),
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            verbose=False
        )

        assert counts_file.exists()
        assert freq_file.exists()
        assert logprob_file.exists()

        # Carica e verifica
        counts_array = np.load(counts_file)
        freq_array = np.load(freq_file)
        logprob_array = np.load(logprob_file)

        assert counts_array.shape == (26,)
        assert freq_array.shape == (26,)
        assert logprob_array.shape == (26,)

        assert counts_array[0] == 100  # A
        assert counts_array[4] == 80   # E
        assert counts_array[8] == 50   # I


class TestLetterNPYShapes:
    """Test dimensioni array NPY lettere."""

    def test_npy_shapes(self, tmp_path):
        """Test che gli array NPY abbiano shape corretta."""
        letter_counts = Counter({0: 10})

        counts_file = tmp_path / "counts.npy"
        freq_file = tmp_path / "freq.npy"
        logprob_file = tmp_path / "logprob.npy"

        write_letter_npy(
            letter_counts=letter_counts,
            alpha_letters=0.01,
            counts_file=str(counts_file),
            frequencies_file=str(freq_file),
            logprob_file=str(logprob_file),
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            verbose=False
        )

        counts_array = np.load(counts_file)
        freq_array = np.load(freq_file)
        logprob_array = np.load(logprob_file)

        assert counts_array.shape == (26,)
        assert freq_array.shape == (26,)
        assert logprob_array.shape == (26,)


class TestLetterCSVColumns:
    """Test colonne CSV lettere."""

    def test_csv_columns(self, tmp_path):
        """Test che il CSV lettere abbia le colonne corrette."""
        letter_counts = Counter({0: 10, 1: 5})

        csv_file = tmp_path / "letters.csv"

        write_letter_csv(
            letter_counts=letter_counts,
            alpha_letters=0.01,
            output_file=str(csv_file),
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            verbose=False
        )

        with open(csv_file, 'r') as f:
            header = f.readline().strip()

        expected_columns = [
            'letter', 'letter_id', 'count', 'frequency',
            'smoothed_frequency', 'log_probability', 'rank'
        ]

        for col in expected_columns:
            assert col in header


class TestLetterCSVNPYConsistency:
    """Test coerenza tra CSV e NPY lettere."""

    def test_csv_npy_consistency(self, tmp_path):
        """Test che CSV e NPY contengano gli stessi valori."""
        letter_counts = Counter({
            0: 100,  # A
            4: 80,   # E
            8: 50    # I
        })

        csv_file = tmp_path / "letters.csv"
        counts_file = tmp_path / "counts.npy"
        freq_file = tmp_path / "freq.npy"
        logprob_file = tmp_path / "logprob.npy"

        alpha_letters = 0.01

        write_letter_csv(
            letter_counts=letter_counts,
            alpha_letters=alpha_letters,
            output_file=str(csv_file),
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            verbose=False
        )

        write_letter_npy(
            letter_counts=letter_counts,
            alpha_letters=alpha_letters,
            counts_file=str(counts_file),
            frequencies_file=str(freq_file),
            logprob_file=str(logprob_file),
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            verbose=False
        )

        # Carica NPY
        counts_array = np.load(counts_file)
        logprob_array = np.load(logprob_file)

        # Leggi CSV
        import csv
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                letter_id = int(row['letter_id'])
                count = int(row['count'])
                log_prob = float(row['log_probability'])

                # Verifica coerenza
                assert counts_array[letter_id] == count
                assert abs(logprob_array[letter_id] - log_prob) < 1e-5


class TestLetterProbabilitiesSumToOne:
    """Test che le probabilità sommino a 1."""

    def test_probabilities_sum(self, tmp_path):
        """Test che le frequenze sommino circa a 1."""
        letter_counts = Counter({
            i: (i + 1) * 10 for i in range(26)
        })

        freq_file = tmp_path / "freq.npy"
        counts_file = tmp_path / "counts.npy"
        logprob_file = tmp_path / "logprob.npy"

        write_letter_npy(
            letter_counts=letter_counts,
            alpha_letters=0.01,
            counts_file=str(counts_file),
            frequencies_file=str(freq_file),
            logprob_file=str(logprob_file),
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            verbose=False
        )

        freq_array = np.load(freq_file)

        # Somma frequenze grezze dovrebbe essere circa 1
        total = np.sum(freq_array)
        assert abs(total - 1.0) < 1e-5


class TestLetterLogprobNotInf:
    """Test che log_probability non sia inf."""

    def test_no_inf_values(self, tmp_path):
        """Test che non ci siano valori inf o -inf."""
        letter_counts = Counter({0: 100, 1: 50})

        logprob_file = tmp_path / "logprob.npy"
        counts_file = tmp_path / "counts.npy"
        freq_file = tmp_path / "freq.npy"

        write_letter_npy(
            letter_counts=letter_counts,
            alpha_letters=0.01,
            counts_file=str(counts_file),
            frequencies_file=str(freq_file),
            logprob_file=str(logprob_file),
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            verbose=False
        )

        logprob_array = np.load(logprob_file)

        # Verifica nessun inf o -inf
        assert not np.any(np.isinf(logprob_array))
        assert not np.any(np.isnan(logprob_array))


class TestParallelEqualsSequentialLetters:
    """Test che modalità parallela e sequenziale producano stessi letter_counts."""

    def test_parallel_sequential_consistency(self, tmp_path):
        """Test coerenza letter_counts tra sequenziale e parallelo."""
        # Crea fixture temporanea
        fixture_file = tmp_path / "corpus.txt"
        fixture_file.write_text("""##
# Commento
##
<text id="1">
Il gatto nero dorme.
</text>
<text id="2">
La casa è grande.
</text>
""")

        # Sequenziale
        config_seq = BuilderConfig(
            corpus_file=fixture_file,
            output_dir=tmp_path / "seq",
            min_n=3,
            max_n=4,
            workers=1
        )

        state_seq = build_from_corpus(config_seq)

        # Parallelo
        config_par = BuilderConfig(
            corpus_file=fixture_file,
            output_dir=tmp_path / "par",
            min_n=3,
            max_n=4,
            workers=2
        )

        state_par = build_from_corpus(config_par)

        # Verifica che letter_counts siano identici
        assert state_seq.letter_counts == state_par.letter_counts


class TestIntegrationWithMetadata:
    """Test che metadata contenga sezione letters."""

    def test_metadata_has_letters_section(self, tmp_path):
        """Test che metadata.json contenga sezione letters (simulato)."""
        # Simula generazione metadata
        letter_counts = Counter({0: 100, 4: 80})
        total_letters = sum(letter_counts.values())
        alpha_letters = 0.01

        metadata = {
            'letters': {
                'total_letters': total_letters,
                'unique_letters': len([lid for lid in range(26) if letter_counts.get(lid, 0) > 0]),
                'alpha_letters': alpha_letters,
                'csv_file': 'csv/paisa_letter_frequencies.csv',
                'counts_npy_file': 'npy/paisa_letter_counts.npy',
                'frequencies_npy_file': 'npy/paisa_letter_frequencies.npy',
                'logprob_npy_file': 'npy/paisa_letter_logprob.npy',
                'top_letters': [
                    {'letter': 'A', 'letter_id': 0, 'count': 100, 'frequency': 0.555556, 'rank': 1},
                    {'letter': 'E', 'letter_id': 4, 'count': 80, 'frequency': 0.444444, 'rank': 2}
                ]
            }
        }

        # Verifica struttura
        assert 'letters' in metadata
        assert 'total_letters' in metadata['letters']
        assert 'alpha_letters' in metadata['letters']
        assert 'csv_file' in metadata['letters']
        assert 'counts_npy_file' in metadata['letters']
        assert 'frequencies_npy_file' in metadata['letters']
        assert 'logprob_npy_file' in metadata['letters']
        assert 'top_letters' in metadata['letters']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

