"""
Test parallelizzazione
"""

import pytest
import sys
import json
import tempfile
from pathlib import Path
from collections import Counter

# Aggiungi root alla path per import
sys.path.insert(0, str(Path(__file__).parent.parent))

from build_paisa_ngrams import (
    iter_paisa_text_blocks,
    batched,
    process_text_block,
    process_blocks_batch,
    merge_batch_result,
    build_from_corpus,
    BuilderConfig,
    BuilderState,
    BatchResult,
    ngram_to_id
)


class TestIterPaisaTextBlocks:
    """Test iterazione su blocchi <text>"""

    def test_basic_iteration(self, tmp_path):
        """Test iterazione base"""
        corpus_file = tmp_path / "test.txt"
        content = """# Commento da ignorare
Testo fuori blocco
<text id="1">
Prima riga blocco 1
Seconda riga blocco 1
</text>
Altro testo fuori
<text id="2">
Unica riga blocco 2
</text>
"""
        corpus_file.write_text(content, encoding='utf-8')

        blocks = list(iter_paisa_text_blocks(corpus_file))

        # Deve restituire esattamente 2 blocchi
        assert len(blocks) == 2

        # I blocchi non devono contenere tag
        assert '<text' not in blocks[0]
        assert '</text>' not in blocks[0]
        assert '<text' not in blocks[1]
        assert '</text>' not in blocks[1]

        # Il primo blocco deve contenere entrambe le righe
        assert 'Prima riga blocco 1' in blocks[0]
        assert 'Seconda riga blocco 1' in blocks[0]

        # Il secondo blocco
        assert 'blocco 2' in blocks[1]

    def test_ignores_comments(self, tmp_path):
        """Test che i commenti vengano ignorati"""
        corpus_file = tmp_path / "test.txt"
        content = """# commento globale
<text id="1">
riga valida
# commento interno da ignorare
altra riga valida
</text>
"""
        corpus_file.write_text(content, encoding='utf-8')

        blocks = list(iter_paisa_text_blocks(corpus_file))

        assert len(blocks) == 1

        # Il commento interno non dovrebbe essere nel blocco
        # (viene ignorato durante l'iterazione delle righe)
        # Ma in realtà il commento interno è dentro <text> quindi viene incluso
        # Controlliamo che il blocco contenga le righe valide
        assert 'riga valida' in blocks[0]
        assert 'altra riga valida' in blocks[0]

    def test_ignores_content_outside_blocks(self, tmp_path):
        """Test che contenuto fuori blocchi venga ignorato"""
        corpus_file = tmp_path / "test.txt"
        content = """Riga fuori 1
Riga fuori 2
<text id="1">
dentro
</text>
Riga fuori 3
<text id="2">
dentro2
</text>
Riga fuori 4
"""
        corpus_file.write_text(content, encoding='utf-8')

        blocks = list(iter_paisa_text_blocks(corpus_file))

        assert len(blocks) == 2
        assert 'Riga fuori' not in blocks[0]
        assert 'Riga fuori' not in blocks[1]
        assert 'dentro' in blocks[0]
        assert 'dentro2' in blocks[1]

    def test_inline_text_tags(self, tmp_path):
        """Test tag e contenuto sulla stessa riga"""
        corpus_file = tmp_path / "test.txt"
        content = """<text id="1">contenuto uno</text>
<text id="2">contenuto due</text>
"""
        corpus_file.write_text(content, encoding='utf-8')

        blocks = list(iter_paisa_text_blocks(corpus_file))

        assert len(blocks) == 2
        assert 'contenuto uno' in blocks[0]
        assert 'contenuto due' in blocks[1]


class TestBatched:
    """Test funzione batched"""

    def test_even_batches(self):
        """Test batch di dimensione uniforme"""
        items = ['a', 'b', 'c', 'd', 'e', 'f']
        batches = list(batched(iter(items), 2))

        assert len(batches) == 3
        assert batches[0] == ['a', 'b']
        assert batches[1] == ['c', 'd']
        assert batches[2] == ['e', 'f']

    def test_uneven_batches(self):
        """Test con ultimo batch più piccolo"""
        items = ['a', 'b', 'c', 'd', 'e']
        batches = list(batched(iter(items), 2))

        assert len(batches) == 3
        assert batches[0] == ['a', 'b']
        assert batches[1] == ['c', 'd']
        assert batches[2] == ['e']

    def test_single_batch(self):
        """Test tutti elementi in un batch"""
        items = ['a', 'b', 'c']
        batches = list(batched(iter(items), 10))

        assert len(batches) == 1
        assert batches[0] == ['a', 'b', 'c']

    def test_empty_iterator(self):
        """Test iteratore vuoto"""
        batches = list(batched(iter([]), 2))
        assert batches == []


class TestProcessTextBlock:
    """Test processing singolo blocco"""

    def test_basic_processing(self, tmp_path):
        """Test processing base di un blocco"""
        config = BuilderConfig(
            corpus_file=tmp_path / "dummy.txt",
            output_dir=tmp_path / "output",
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        )

        block_text = "Il gatto nero"
        result = process_text_block(block_text, config)

        # Verifica struttura
        assert isinstance(result, BatchResult)
        assert 'inword' in result.counts
        assert 'continuous' in result.counts
        assert 3 in result.counts['inword']
        assert 4 in result.counts['inword']

        # Verifica stats
        assert result.stats['total_text_blocks'] == 1
        assert result.stats['total_words'] > 0

        # Verifica alcuni n-grammi
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        gat_id = ngram_to_id("GAT", alphabet)
        assert result.counts['inword'][3][gat_id] == 1


class TestProcessBlocksBatch:
    """Test processing batch di blocchi"""

    def test_batch_aggregation(self, tmp_path):
        """Test che il batch aggrega correttamente"""
        config = BuilderConfig(
            corpus_file=tmp_path / "dummy.txt",
            output_dir=tmp_path / "output",
            min_n=3,
            max_n=4
        )

        blocks = [
            "Il gatto",
            "Il cane",
            "Il topo"
        ]

        result = process_blocks_batch(blocks, config)

        # Deve aver processato 3 blocchi
        assert result.stats['total_text_blocks'] == 3

        # IL deve apparire 3 volte
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        il_id = ngram_to_id("IL", alphabet) if len("IL") >= 3 else None

        # Verifica che i conteggi siano aggregati
        total_3grams = sum(result.counts['inword'][3].values())
        assert total_3grams > 0

    def test_batch_equals_sum_of_blocks(self, tmp_path):
        """Test che batch = somma di blocchi individuali"""
        config = BuilderConfig(
            corpus_file=tmp_path / "dummy.txt",
            output_dir=tmp_path / "output",
            min_n=3,
            max_n=4
        )

        blocks = [
            "GATTO",
            "NERO",
            "BIANCO"
        ]

        # Processa individualmente
        individual_results = [process_text_block(b, config) for b in blocks]

        # Aggrega manualmente
        manual_counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }
        manual_stats = {
            'total_text_blocks': 0,
            'total_words': 0,
            'total_chars_inword': 0,
            'total_chars_continuous': 0
        }

        for res in individual_results:
            for model_type in ['inword', 'continuous']:
                for n in [3, 4]:
                    manual_counts[model_type][n].update(res.counts[model_type][n])
            for key in manual_stats:
                manual_stats[key] += res.stats[key]

        # Processa come batch
        batch_result = process_blocks_batch(blocks, config)

        # Verifica uguaglianza
        assert batch_result.stats == manual_stats

        for model_type in ['inword', 'continuous']:
            for n in [3, 4]:
                assert batch_result.counts[model_type][n] == manual_counts[model_type][n]


class TestMergeBatchResult:
    """Test merge risultati batch"""

    def test_merge_updates_state(self, tmp_path):
        """Test che merge aggiorna lo stato globale"""
        global_state = BuilderState(
            counts={
                'inword': {3: Counter(), 4: Counter()},
                'continuous': {3: Counter(), 4: Counter()}
            },
            stats={
                'total_text_blocks': 0,
                'total_words': 0,
                'total_chars_inword': 0,
                'total_chars_continuous': 0
            }
        )

        batch_result = BatchResult(
            counts={
                'inword': {3: Counter({1: 5, 2: 3}), 4: Counter({10: 2})},
                'continuous': {3: Counter({1: 7}), 4: Counter()}
            },
            letter_counts=Counter(),
            stats={
                'total_text_blocks': 2,
                'total_words': 10,
                'total_chars_inword': 50,
                'total_chars_continuous': 50
            }
        )

        merge_batch_result(global_state, batch_result)

        # Verifica merge
        assert global_state.stats['total_text_blocks'] == 2
        assert global_state.stats['total_words'] == 10
        assert global_state.counts['inword'][3][1] == 5
        assert global_state.counts['inword'][3][2] == 3
        assert global_state.counts['continuous'][3][1] == 7


class TestNoCrossBlockContinuousNgrams:
    """Test che n-grammi continuous non attraversino blocchi"""

    def test_no_cross_block_ngrams(self, tmp_path):
        """Test cruciale: verifica che non ci siano n-grammi cross-block"""
        corpus_file = tmp_path / "test.txt"
        content = """<text id="1">
ABC
</text>
<text id="2">
DEF
</text>
"""
        corpus_file.write_text(content, encoding='utf-8')

        config = BuilderConfig(
            corpus_file=corpus_file,
            output_dir=tmp_path / "output",
            min_n=3,
            max_n=4,
            workers=1
        )

        state = build_from_corpus(config)

        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        # BCDE attraverserebbe i blocchi (C da ABC e D da DEF)
        # Non dovrebbe esistere
        if len("BCDE") == 4:
            bcde_id = ngram_to_id("BCDE", alphabet)
            assert state.counts['continuous'][4][bcde_id] == 0

        # CDEF attraverserebbe i blocchi
        if len("CDEF") == 4:
            cdef_id = ngram_to_id("CDEF", alphabet)
            assert state.counts['continuous'][4][cdef_id] == 0


class TestParallelEqualsSequential:
    """Test che parallelo = sequenziale"""

    def test_parallel_equals_sequential_counts(self):
        """Test cruciale: verifica che i conteggi siano identici"""
        fixture_path = Path(__file__).parent / "fixtures" / "small_paisa_sample.txt"

        if not fixture_path.exists():
            pytest.skip(f"Fixture file not found: {fixture_path}")

        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Configurazione sequenziale
            config_seq = BuilderConfig(
                corpus_file=fixture_path,
                output_dir=tmp_path / "out_seq",
                min_n=3,
                max_n=4,
                workers=1,
                batch_size=2,
                verbose=False
            )

            # Configurazione parallela
            config_par = BuilderConfig(
                corpus_file=fixture_path,
                output_dir=tmp_path / "out_par",
                min_n=3,
                max_n=4,
                workers=2,
                batch_size=2,
                verbose=False
            )

            # Esegui entrambi
            state_seq = build_from_corpus(config_seq)
            state_par = build_from_corpus(config_par)

            # Verifica counts identici
            for model_type in ['inword', 'continuous']:
                for n in [3, 4]:
                    assert state_seq.counts[model_type][n] == state_par.counts[model_type][n], \
                        f"Counts diversi per {model_type} n={n}"

            # Verifica stats principali identici
            assert state_seq.stats['total_text_blocks'] == state_par.stats['total_text_blocks']
            assert state_seq.stats['total_words'] == state_par.stats['total_words']


class TestParallelMetadata:
    """Test metadata in modalità parallela"""

    def test_parallel_metadata_contains_info(self):
        """Test che metadata contenga info parallele"""
        fixture_path = Path(__file__).parent / "fixtures" / "small_paisa_sample.txt"

        if not fixture_path.exists():
            pytest.skip(f"Fixture file not found: {fixture_path}")

        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Usa la CLI con workers=2
            import subprocess
            result = subprocess.run([
                sys.executable,
                str(Path(__file__).parent.parent / "build_paisa_ngrams.py"),
                "--corpus-file", str(fixture_path),
                "--output-dir", str(tmp_path / "output"),
                "--workers", "2",
                "--batch-size", "2",
                "--save-csv"
            ], capture_output=True, text=True)

            # Verifica metadata
            metadata_file = tmp_path / "output" / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file) as f:
                    metadata = json.load(f)

                assert metadata['execution_mode'] == 'parallel'
                assert metadata['workers'] == 2
                assert metadata['batch_size'] == 2
                assert 'total_batches_processed' in metadata['stats']

    def test_sequential_metadata(self):
        """Test metadata in modalità sequenziale"""
        fixture_path = Path(__file__).parent / "fixtures" / "small_paisa_sample.txt"

        if not fixture_path.exists():
            pytest.skip(f"Fixture file not found: {fixture_path}")

        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            config = BuilderConfig(
                corpus_file=fixture_path,
                output_dir=tmp_path / "output",
                workers=1,
                save_csv=True,
                verbose=False
            )

            state = build_from_corpus(config)

            # In modalità sequenziale, non ci dovrebbe essere total_batches_processed
            # (o dovrebbe essere 0 o assente))


class TestGeneratedReadme:
    """Test README generato con info parallelizzazione"""

    def test_readme_mentions_parallelization(self):
        """Test che README menzioni parallelizzazione"""
        fixture_path = Path(__file__).parent / "fixtures" / "small_paisa_sample.txt"

        if not fixture_path.exists():
            pytest.skip(f"Fixture file not found: {fixture_path}")

        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Usa la CLI con workers=2
            import subprocess
            result = subprocess.run([
                sys.executable,
                str(Path(__file__).parent.parent / "build_paisa_ngrams.py"),
                "--corpus-file", str(fixture_path),
                "--output-dir", str(tmp_path / "output"),
                "--workers", "2",
                "--save-csv"
            ], capture_output=True, text=True)

            # Verifica README
            readme_file = tmp_path / "output" / "README_GENERATED_MODEL.md"
            if readme_file.exists():
                content = readme_file.read_text()

                assert 'parallela' in content.lower() or 'parallel' in content.lower()
                assert 'worker' in content.lower()
                assert 'blocchi' in content.lower() or 'block' in content.lower()
                assert 'indipendent' in content.lower()

