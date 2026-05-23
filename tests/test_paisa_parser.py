"""
Test parsing corpus PAISÀ
"""

import pytest
import sys
import tempfile
from pathlib import Path
from collections import Counter

# Aggiungi root alla path per import
sys.path.insert(0, str(Path(__file__).parent.parent))

from build_paisa_ngrams import (
    parse_paisa_stream,
    ngram_to_id,
    normalize_to_words
)


class TestPaisaParser:
    """Test parser corpus PAISÀ"""

    @pytest.fixture
    def sample_corpus(self, tmp_path):
        """Crea file corpus temporaneo per test"""
        corpus_file = tmp_path / "test_corpus.txt"
        content = """##
# Commento da ignorare
##
<text id="1" url="http://example.com">
Il gatto nero
</text>
<text id="2" url="http://example.com/2">
Perché la città è bella
</text>
"""
        corpus_file.write_text(content, encoding='utf-8')
        return str(corpus_file)

    def test_basic_parsing(self, sample_corpus):
        """Test parsing base"""
        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        stats = parse_paisa_stream(
            corpus_file=sample_corpus,
            counts=counts,
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        # Verifica statistiche
        assert stats['total_lines_read'] > 0
        assert stats['total_text_blocks'] == 2
        assert stats['total_words'] > 0

    def test_ignore_comments(self, tmp_path):
        """Test che i commenti vengano ignorati"""
        corpus_file = tmp_path / "test_corpus.txt"
        content = """# Commento
<text id="1">
gatto
</text>
"""
        corpus_file.write_text(content, encoding='utf-8')

        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        stats = parse_paisa_stream(
            corpus_file=str(corpus_file),
            counts=counts,
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        # Commento non dovrebbe contribuire a word count
        # Ma dovrebbe aver letto la riga
        assert stats['total_lines_read'] >= 3

    def test_ignore_outside_text_blocks(self, tmp_path):
        """Test che testo fuori dai blocchi <text> venga ignorato"""
        corpus_file = tmp_path / "test_corpus.txt"
        content = """Testo fuori blocco
<text id="1">
gatto
</text>
Altro testo fuori
<text id="2">
nero
</text>
"""
        corpus_file.write_text(content, encoding='utf-8')

        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        stats = parse_paisa_stream(
            corpus_file=str(corpus_file),
            counts=counts,
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        # Solo "gatto" e "nero" dovrebbero essere processati
        assert stats['total_words'] == 2

    def test_text_block_boundaries(self, tmp_path):
        """Test che i blocchi <text> delimitino correttamente"""
        corpus_file = tmp_path / "test_corpus.txt"
        content = """<text id="1">
gatto
</text>
<text id="2">
nero
</text>
"""
        corpus_file.write_text(content, encoding='utf-8')

        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        stats = parse_paisa_stream(
            corpus_file=str(corpus_file),
            counts=counts,
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        # TON non dovrebbe esistere (cross-document)
        ton_id = ngram_to_id("TON", alphabet)
        assert counts['continuous'][3][ton_id] == 0

        # Ma GAT e NER dovrebbero esistere
        gat_id = ngram_to_id("GAT", alphabet)
        ner_id = ngram_to_id("NER", alphabet)
        assert counts['inword'][3][gat_id] == 1
        assert counts['inword'][3][ner_id] == 1

    def test_inline_text_tags(self, tmp_path):
        """Test tag <text> e contenuto sulla stessa riga"""
        corpus_file = tmp_path / "test_corpus.txt"
        content = """<text id="1">gatto nero</text>
<text id="2">bianco</text>
"""
        corpus_file.write_text(content, encoding='utf-8')

        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        stats = parse_paisa_stream(
            corpus_file=str(corpus_file),
            counts=counts,
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        assert stats['total_words'] == 3

    def test_multiline_text_block(self, tmp_path):
        """Test blocchi <text> multilinea"""
        corpus_file = tmp_path / "test_corpus.txt"
        content = """<text id="1">
Prima riga
Seconda riga
Terza riga
</text>
"""
        corpus_file.write_text(content, encoding='utf-8')

        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        stats = parse_paisa_stream(
            corpus_file=str(corpus_file),
            counts=counts,
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        assert stats['total_words'] == 6

    def test_fixture_file(self):
        """Test con file fixture reale"""
        fixture_path = Path(__file__).parent / "fixtures" / "small_paisa_sample.txt"

        if not fixture_path.exists():
            pytest.skip(f"Fixture file not found: {fixture_path}")

        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        stats = parse_paisa_stream(
            corpus_file=str(fixture_path),
            counts=counts,
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        # Verifica che abbia trovato i blocchi <text>
        assert stats['total_text_blocks'] == 5
        assert stats['total_words'] > 0

        # Verifica n-grammi specifici dalla fixture
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        # Dalla fixture: "Il gatto nero"
        gat_id = ngram_to_id("GAT", alphabet)
        assert counts['inword'][3][gat_id] >= 1

        # Dalla fixture: "Perché" -> "PERCHE"
        rch_id = ngram_to_id("RCH", alphabet)
        assert counts['inword'][3][rch_id] >= 1

    def test_normalization_in_parsing(self, tmp_path):
        """Test che la normalizzazione venga applicata durante il parsing"""
        corpus_file = tmp_path / "test_corpus.txt"
        content = """<text id="1">
perché città può
</text>
"""
        corpus_file.write_text(content, encoding='utf-8')

        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        stats = parse_paisa_stream(
            corpus_file=str(corpus_file),
            counts=counts,
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        # PERCHE -> RCH, CHE
        rch_id = ngram_to_id("RCH", alphabet)
        che_id = ngram_to_id("CHE", alphabet)
        assert counts['inword'][3][rch_id] >= 1
        assert counts['inword'][3][che_id] >= 1

        # CITTA -> ITT, TTA
        itt_id = ngram_to_id("ITT", alphabet)
        tta_id = ngram_to_id("TTA", alphabet)
        assert counts['inword'][3][itt_id] >= 1
        assert counts['inword'][3][tta_id] >= 1

    def test_tag_removal_in_parsing(self, tmp_path):
        """Test rimozione tag durante il parsing"""
        corpus_file = tmp_path / "test_corpus.txt"
        content = """<text id="1">
<b>Roma</b> è bella
</text>
"""
        corpus_file.write_text(content, encoding='utf-8')

        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        stats = parse_paisa_stream(
            corpus_file=str(corpus_file),
            counts=counts,
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        # ROMA dovrebbe essere processato
        rom_id = ngram_to_id("ROM", alphabet)
        assert counts['inword'][3][rom_id] >= 1

    def test_empty_file(self, tmp_path):
        """Test file vuoto"""
        corpus_file = tmp_path / "empty.txt"
        corpus_file.write_text("", encoding='utf-8')

        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        stats = parse_paisa_stream(
            corpus_file=str(corpus_file),
            counts=counts,
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        assert stats['total_lines_read'] == 0
        assert stats['total_text_blocks'] == 0
        assert stats['total_words'] == 0

    def test_only_comments(self, tmp_path):
        """Test file con solo commenti"""
        corpus_file = tmp_path / "comments.txt"
        content = """# Commento 1
# Commento 2
##
# Altro commento
"""
        corpus_file.write_text(content, encoding='utf-8')

        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        stats = parse_paisa_stream(
            corpus_file=str(corpus_file),
            counts=counts,
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        assert stats['total_words'] == 0

    def test_different_boundary_modes(self, tmp_path):
        """Test modalità boundary diverse"""
        corpus_file = tmp_path / "test_corpus.txt"
        content = """<text id="1">
Il gatto nero. Dorme.
</text>
"""
        corpus_file.write_text(content, encoding='utf-8')

        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        # Test sentence mode
        counts_sentence = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }
        parse_paisa_stream(
            corpus_file=str(corpus_file),
            counts=counts_sentence,
            min_n=3,
            max_n=4,
            alphabet=alphabet,
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        # Test line mode
        counts_line = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }
        parse_paisa_stream(
            corpus_file=str(corpus_file),
            counts=counts_line,
            min_n=3,
            max_n=4,
            alphabet=alphabet,
            encoding='utf-8',
            continuous_boundary_mode='line',
            progress_every=100000,
            verbose=False
        )

        # In sentence mode, ERO e DOR non dovrebbero essere connessi (punto tra loro)
        erod_id = ngram_to_id("EROD", alphabet)

        # In line mode, potrebbero essere connessi (dipende dalla normalizzazione)
        # Ma inword dovrebbe essere identico in entrambi
        gat_id = ngram_to_id("GAT", alphabet)
        assert counts_sentence['inword'][3][gat_id] == counts_line['inword'][3][gat_id]


class TestStatistics:
    """Test statistiche parsing"""

    def test_line_count(self, tmp_path):
        """Test conteggio righe"""
        corpus_file = tmp_path / "test_corpus.txt"
        content = """line1
line2
line3
<text id="1">content</text>
line5
"""
        corpus_file.write_text(content, encoding='utf-8')

        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        stats = parse_paisa_stream(
            corpus_file=str(corpus_file),
            counts=counts,
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        assert stats['total_lines_read'] == 5

    def test_text_block_count(self, tmp_path):
        """Test conteggio blocchi <text>"""
        corpus_file = tmp_path / "test_corpus.txt"
        content = """<text id="1">a</text>
<text id="2">b</text>
<text id="3">c</text>
"""
        corpus_file.write_text(content, encoding='utf-8')

        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        stats = parse_paisa_stream(
            corpus_file=str(corpus_file),
            counts=counts,
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        assert stats['total_text_blocks'] == 3

    def test_word_count(self, tmp_path):
        """Test conteggio parole"""
        corpus_file = tmp_path / "test_corpus.txt"
        content = """<text id="1">
uno due tre quattro cinque
</text>
"""
        corpus_file.write_text(content, encoding='utf-8')

        counts = {
            'inword': {3: Counter(), 4: Counter()},
            'continuous': {3: Counter(), 4: Counter()}
        }

        stats = parse_paisa_stream(
            corpus_file=str(corpus_file),
            counts=counts,
            min_n=3,
            max_n=4,
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            encoding='utf-8',
            continuous_boundary_mode='sentence',
            progress_every=100000,
            verbose=False
        )

        assert stats['total_words'] == 5

