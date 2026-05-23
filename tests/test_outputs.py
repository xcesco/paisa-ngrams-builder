"""
Test output (CSV, NPY, metadata, README)
"""

import pytest
import sys
import json
import csv
import tempfile
from pathlib import Path
from collections import Counter

# Aggiungi root alla path per import
sys.path.insert(0, str(Path(__file__).parent.parent))

from build_paisa_ngrams import (
    build_probability_arrays,
    write_csv,
    write_npy,
    write_metadata,
    write_generated_model_readme,
    ngram_to_id,
    id_to_ngram
)


class TestBuildProbabilityArrays:
    """Test costruzione array probabilità"""

    def test_basic_probability_calculation(self):
        """Test calcolo probabilità base"""
        counts = {
            'inword': {3: Counter()},
            'continuous': {3: Counter()}
        }

        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        # Aggiungi alcuni n-grammi
        counts['inword'][3][ngram_to_id("GAT", alphabet)] = 10
        counts['inword'][3][ngram_to_id("TTO", alphabet)] = 5

        models = build_probability_arrays(
            counts=counts,
            alphabet=alphabet,
            alpha=0.01,
            verbose=False
        )

        # Verifica struttura
        assert 'inword' in models
        assert 3 in models['inword']

        model = models['inword'][3]

        # Verifica statistiche
        assert model['total_ngrams'] == 15  # 10 + 5
        assert model['unique_ngrams'] == 2
        assert model['vocab_size'] == 26**3

        # Verifica default log probability
        assert 'default_log_probability' in model
        assert model['default_log_probability'] < 0  # Log di probabilità < 1

        # Verifica array
        assert 'logprob_array' in model
        assert 'counts_array' in model

    def test_array_sizes(self):
        """Test dimensioni array"""
        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        counts['inword'][3][0] = 1  # Dummy data
        counts['inword'][4][0] = 1

        models = build_probability_arrays(
            counts=counts,
            alphabet=alphabet,
            alpha=0.01,
            verbose=False
        )

        # Verifica dimensioni array trigrammi
        assert len(models['inword'][3]['logprob_array']) == 26**3
        assert len(models['inword'][3]['counts_array']) == 26**3

        # Verifica dimensioni array quadrigrammi
        assert len(models['inword'][4]['logprob_array']) == 26**4
        assert len(models['inword'][4]['counts_array']) == 26**4

    def test_csv_data_structure(self):
        """Test struttura dati CSV"""
        counts = {
            'inword': {3: Counter()},
            'continuous': {3: Counter()}
        }

        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        counts['inword'][3][ngram_to_id("GAT", alphabet)] = 10

        models = build_probability_arrays(
            counts=counts,
            alphabet=alphabet,
            alpha=0.01,
            verbose=False
        )

        csv_data = models['inword'][3]['csv_data']

        # Verifica che abbiamo dati
        assert len(csv_data) == 1

        # Verifica campi richiesti
        item = csv_data[0]
        required_fields = [
            'ngram', 'ngram_id', 'count',
            'probability', 'smoothed_probability',
            'log_probability', 'rank'
        ]
        for field in required_fields:
            assert field in item

        # Verifica valori
        assert item['ngram'] == "GAT"
        assert item['count'] == 10
        assert item['rank'] == 1  # È il primo (e unico)

    def test_rank_ordering(self):
        """Test ordinamento per rank"""
        counts = {
            'inword': {3: Counter()},
            'continuous': {3: Counter()}
        }

        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        counts['inword'][3][ngram_to_id("GAT", alphabet)] = 100
        counts['inword'][3][ngram_to_id("TTO", alphabet)] = 50
        counts['inword'][3][ngram_to_id("ONE", alphabet)] = 75

        models = build_probability_arrays(
            counts=counts,
            alphabet=alphabet,
            alpha=0.01,
            verbose=False
        )

        csv_data = models['inword'][3]['csv_data']

        # Verifica ordinamento per count
        assert csv_data[0]['count'] >= csv_data[1]['count']
        assert csv_data[1]['count'] >= csv_data[2]['count']

        # Verifica rank
        assert csv_data[0]['rank'] == 1
        assert csv_data[1]['rank'] == 2
        assert csv_data[2]['rank'] == 3

        # Il più frequente dovrebbe essere GAT
        assert csv_data[0]['ngram'] == "GAT"


class TestWriteCSV:
    """Test scrittura CSV"""

    def test_csv_file_creation(self, tmp_path):
        """Test creazione file CSV"""
        csv_file = tmp_path / "test.csv"

        csv_data = [
            {
                'ngram': 'GAT',
                'ngram_id': 4075,
                'count': 100,
                'probability': 0.1,
                'smoothed_probability': 0.099,
                'log_probability': -2.31,
                'rank': 1
            }
        ]

        write_csv(
            csv_data=csv_data,
            output_file=str(csv_file),
            n=3,
            model_type='inword',
            min_count=1,
            verbose=False
        )

        assert csv_file.exists()

        # Leggi e verifica contenuto
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]['ngram'] == 'GAT'
        assert rows[0]['n'] == '3'
        assert rows[0]['model'] == 'inword'

    def test_csv_min_count_filter(self, tmp_path):
        """Test filtro min_count"""
        csv_file = tmp_path / "test.csv"

        csv_data = [
            {
                'ngram': 'GAT',
                'ngram_id': 4075,
                'count': 100,
                'probability': 0.1,
                'smoothed_probability': 0.099,
                'log_probability': -2.31,
                'rank': 1
            },
            {
                'ngram': 'TTO',
                'ngram_id': 1234,
                'count': 2,
                'probability': 0.01,
                'smoothed_probability': 0.009,
                'log_probability': -4.71,
                'rank': 2
            }
        ]

        # Con min_count=5, solo GAT dovrebbe passare
        write_csv(
            csv_data=csv_data,
            output_file=str(csv_file),
            n=3,
            model_type='inword',
            min_count=5,
            verbose=False
        )

        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]['ngram'] == 'GAT'

    def test_csv_headers(self, tmp_path):
        """Test header CSV"""
        csv_file = tmp_path / "test.csv"

        csv_data = [
            {
                'ngram': 'GAT',
                'ngram_id': 4075,
                'count': 100,
                'probability': 0.1,
                'smoothed_probability': 0.099,
                'log_probability': -2.31,
                'rank': 1
            }
        ]

        write_csv(
            csv_data=csv_data,
            output_file=str(csv_file),
            n=3,
            model_type='inword',
            min_count=1,
            verbose=False
        )

        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames

        expected_headers = [
            'ngram', 'ngram_id', 'n', 'model',
            'count', 'probability', 'smoothed_probability',
            'log_probability', 'rank'
        ]

        assert headers == expected_headers


class TestWriteNPY:
    """Test scrittura NPY"""

    def test_npy_file_creation(self, tmp_path):
        """Test creazione file NPY"""
        import numpy as np

        logprob_file = tmp_path / "logprob.npy"
        counts_file = tmp_path / "counts.npy"

        # Crea array di test
        logprob_array = np.full(100, -5.0, dtype=np.float32)
        counts_array = np.zeros(100, dtype=np.uint64)

        write_npy(
            logprob_array=logprob_array,
            counts_array=counts_array,
            logprob_file=str(logprob_file),
            counts_file=str(counts_file),
            verbose=False
        )

        assert logprob_file.exists()
        assert counts_file.exists()

        # Verifica caricamento
        loaded_logprob = np.load(logprob_file)
        loaded_counts = np.load(counts_file)

        assert len(loaded_logprob) == 100
        assert len(loaded_counts) == 100
        assert loaded_logprob.dtype == np.float32
        assert loaded_counts.dtype == np.uint64

    def test_npy_array_content(self, tmp_path):
        """Test contenuto array NPY"""
        import numpy as np

        logprob_file = tmp_path / "logprob.npy"
        counts_file = tmp_path / "counts.npy"

        # Crea array con valori specifici
        logprob_array = np.full(26**3, -10.0, dtype=np.float32)
        counts_array = np.zeros(26**3, dtype=np.uint64)

        # Imposta alcuni valori
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        gat_id = ngram_to_id("GAT", alphabet)

        logprob_array[gat_id] = -2.5
        counts_array[gat_id] = 100

        write_npy(
            logprob_array=logprob_array,
            counts_array=counts_array,
            logprob_file=str(logprob_file),
            counts_file=str(counts_file),
            verbose=False
        )

        # Ricarica e verifica
        loaded_logprob = np.load(logprob_file)
        loaded_counts = np.load(counts_file)

        assert loaded_logprob[gat_id] == -2.5
        assert loaded_counts[gat_id] == 100


class TestWriteMetadata:
    """Test scrittura metadata"""

    def test_metadata_file_creation(self, tmp_path):
        """Test creazione file metadata"""
        metadata_file = tmp_path / "metadata.json"

        metadata = {
            'corpus': 'TEST',
            'alpha': 0.01,
            'models': {
                '3_inword': {
                    'total_ngrams': 1000,
                    'unique_ngrams': 500
                }
            }
        }

        write_metadata(
            metadata=metadata,
            output_file=str(metadata_file),
            verbose=False
        )

        assert metadata_file.exists()

        # Verifica contenuto
        with open(metadata_file, 'r') as f:
            loaded = json.load(f)

        assert loaded['corpus'] == 'TEST'
        assert loaded['alpha'] == 0.01
        assert '3_inword' in loaded['models']

    def test_metadata_json_format(self, tmp_path):
        """Test formato JSON metadata"""
        metadata_file = tmp_path / "metadata.json"

        metadata = {
            'test_field': 'test_value',
            'test_number': 123,
            'test_list': [1, 2, 3]
        }

        write_metadata(
            metadata=metadata,
            output_file=str(metadata_file),
            verbose=False
        )

        # Verifica che sia JSON valido
        with open(metadata_file, 'r') as f:
            content = f.read()
            loaded = json.loads(content)

        assert loaded == metadata


class TestWriteGeneratedReadme:
    """Test scrittura README generato"""

    def test_readme_creation(self, tmp_path):
        """Test creazione README"""
        readme_file = tmp_path / "README.md"

        metadata = {
            'corpus': 'TEST',
            'corpus_file': 'test.txt',
            'output_dir': 'output',
            'alphabet': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
            'alpha': 0.01,
            'continuous_boundary_mode': 'sentence',
            'generation_date': '2024-01-01',
            'stats': {
                'total_lines_read': 1000,
                'total_text_blocks': 100,
                'total_words': 5000
            },
            'models': {
                '3_inword': {
                    'total_ngrams': 10000,
                    'unique_ngrams': 5000,
                    'vocab_size': 17576,
                    'default_log_probability': -10.5,
                    'csv_file': 'csv/test.csv',
                    'logprob_npy_file': 'npy/test_logprob.npy',
                    'counts_npy_file': 'npy/test_counts.npy'
                },
                '4_inword': {
                    'total_ngrams': 10000,
                    'unique_ngrams': 5000,
                    'vocab_size': 456976,
                    'default_log_probability': -12.5,
                    'csv_file': 'csv/test.csv',
                    'logprob_npy_file': 'npy/test_logprob.npy',
                    'counts_npy_file': 'npy/test_counts.npy'
                },
                '3_continuous': {
                    'total_ngrams': 15000,
                    'unique_ngrams': 7000,
                    'vocab_size': 17576,
                    'default_log_probability': -10.0,
                    'csv_file': 'csv/test.csv',
                    'logprob_npy_file': 'npy/test_logprob.npy',
                    'counts_npy_file': 'npy/test_counts.npy'
                },
                '4_continuous': {
                    'total_ngrams': 15000,
                    'unique_ngrams': 7000,
                    'vocab_size': 456976,
                    'default_log_probability': -12.0,
                    'csv_file': 'csv/test.csv',
                    'logprob_npy_file': 'npy/test_logprob.npy',
                    'counts_npy_file': 'npy/test_counts.npy'
                }
            },
            'letters': {
                'total_letters': 50000,
                'unique_letters': 26,
                'alpha_letters': 0.01,
                'csv_file': 'csv/paisa_letter_frequencies.csv',
                'counts_npy_file': 'npy/paisa_letter_counts.npy',
                'frequencies_npy_file': 'npy/paisa_letter_frequencies.npy',
                'logprob_npy_file': 'npy/paisa_letter_logprob.npy',
                'top_letters': []
            }
        }

        write_generated_model_readme(
            metadata=metadata,
            output_file=str(readme_file),
            verbose=False
        )

        assert readme_file.exists()

    def test_readme_content(self, tmp_path):
        """Test contenuto README"""
        readme_file = tmp_path / "README.md"

        metadata = {
            'corpus': 'TEST_CORPUS',
            'corpus_file': 'test.txt',
            'output_dir': 'output',
            'alphabet': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
            'alpha': 0.01,
            'continuous_boundary_mode': 'sentence',
            'generation_date': '2024-01-01',
            'stats': {
                'total_lines_read': 1000,
                'total_text_blocks': 100,
                'total_words': 5000
            },
            'models': {
                '3_inword': {
                    'total_ngrams': 10000,
                    'unique_ngrams': 5000,
                    'vocab_size': 17576,
                    'default_log_probability': -10.5,
                    'csv_file': 'csv/test.csv',
                    'logprob_npy_file': 'npy/test_logprob.npy',
                    'counts_npy_file': 'npy/test_counts.npy'
                },
                '4_inword': {
                    'total_ngrams': 10000,
                    'unique_ngrams': 5000,
                    'vocab_size': 456976,
                    'default_log_probability': -12.5,
                    'csv_file': 'csv/test.csv',
                    'logprob_npy_file': 'npy/test_logprob.npy',
                    'counts_npy_file': 'npy/test_counts.npy'
                },
                '3_continuous': {
                    'total_ngrams': 15000,
                    'unique_ngrams': 7000,
                    'vocab_size': 17576,
                    'default_log_probability': -10.0,
                    'csv_file': 'csv/test.csv',
                    'logprob_npy_file': 'npy/test_logprob.npy',
                    'counts_npy_file': 'npy/test_counts.npy'
                },
                '4_continuous': {
                    'total_ngrams': 15000,
                    'unique_ngrams': 7000,
                    'vocab_size': 456976,
                    'default_log_probability': -12.0,
                    'csv_file': 'csv/test.csv',
                    'logprob_npy_file': 'npy/test_logprob.npy',
                    'counts_npy_file': 'npy/test_counts.npy'
                }
            },
            'letters': {
                'total_letters': 50000,
                'unique_letters': 26,
                'alpha_letters': 0.01,
                'csv_file': 'csv/paisa_letter_frequencies.csv',
                'counts_npy_file': 'npy/paisa_letter_counts.npy',
                'frequencies_npy_file': 'npy/paisa_letter_frequencies.npy',
                'logprob_npy_file': 'npy/paisa_letter_logprob.npy',
                'top_letters': []
            }
        }

        write_generated_model_readme(
            metadata=metadata,
            output_file=str(readme_file),
            verbose=False
        )

        # Leggi contenuto
        content = readme_file.read_text()

        # Verifica sezioni chiave
        assert '# Modello n-grammi' in content
        assert 'TEST_CORPUS' in content
        assert 'alpha' in content.lower()
        assert 'smoothing' in content.lower()
        assert 'np.load' in content  # Esempio codice
        assert 'base 26' in content.lower()


class TestCSVNPYCoherence:
    """Test coerenza tra CSV e NPY"""

    def test_csv_npy_values_match(self):
        """Test che valori CSV e NPY corrispondano"""
        import numpy as np

        counts = {
            'inword': {3: Counter()},
            'continuous': {3: Counter()}
        }

        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        # Aggiungi n-grammi noti
        gat_id = ngram_to_id("GAT", alphabet)
        tto_id = ngram_to_id("TTO", alphabet)

        counts['inword'][3][gat_id] = 100
        counts['inword'][3][tto_id] = 50

        models = build_probability_arrays(
            counts=counts,
            alphabet=alphabet,
            alpha=0.01,
            verbose=False
        )

        model = models['inword'][3]

        # Verifica che CSV e NPY siano coerenti
        for csv_row in model['csv_data']:
            ngram_id = csv_row['ngram_id']

            # Count dovrebbe corrispondere
            assert model['counts_array'][ngram_id] == csv_row['count']

            # Log probability dovrebbe corrispondere (entro tolleranza)
            npy_logprob = model['logprob_array'][ngram_id]
            csv_logprob = csv_row['log_probability']

            assert abs(npy_logprob - csv_logprob) < 1e-5

    def test_unobserved_ngrams_have_default_value(self):
        """Test che n-grammi non osservati abbiano valore default"""
        import numpy as np

        counts = {
            'inword': {3: Counter()},
            'continuous': {3: Counter()}
        }

        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        # Aggiungi solo un n-gramma
        gat_id = ngram_to_id("GAT", alphabet)
        counts['inword'][3][gat_id] = 100

        models = build_probability_arrays(
            counts=counts,
            alphabet=alphabet,
            alpha=0.01,
            verbose=False
        )

        model = models['inword'][3]
        default_logprob = model['default_log_probability']

        # N-gramma non osservato
        qzx_id = ngram_to_id("QZX", alphabet)

        # Dovrebbe avere valore default
        assert model['logprob_array'][qzx_id] == default_logprob
        assert model['counts_array'][qzx_id] == 0

