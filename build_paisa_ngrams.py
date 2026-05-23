#!/usr/bin/env python3
"""
N-gram Builder per corpus PAISÀ - Crittoanalisi Vigenère

Costruisce modelli statistici di trigrammi e quadrigrammi italiani
per lo scoring di plaintext candidati durante attacchi al cifrario di Vigenère e Playfair.
"""

import argparse
import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed, wait, FIRST_COMPLETED
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Tuple, Dict, Any, Optional


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class BuilderConfig:
    """Configurazione per il builder n-grammi."""
    corpus_file: Path
    output_dir: Path
    min_n: int = 3
    max_n: int = 4
    alphabet: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    invalid_word_policy: str = "drop-word"  # 'drop-word' scarta parole con caratteri non in alphabet
    alpha: float = 0.01
    alpha_letters: Optional[float] = None  # Se None, usa alpha
    min_count: int = 1
    encoding: str = "utf-8"
    continuous_boundary_mode: str = "sentence"
    save_csv: bool = False
    save_npy: bool = False
    workers: int = 1
    batch_size: int = 1000
    max_pending_batches: Optional[int] = None
    progress_every: int = 100000
    verbose: bool = False


@dataclass
class BatchResult:
    """Risultato del processing di un batch di blocchi."""
    counts: Dict[str, Dict[int, Counter]]
    letter_counts: Counter  # Counter per lettere A-Z (indicizzato da 0-25)
    stats: Dict[str, int]
    
    
@dataclass
class BuilderState:
    """Stato globale del builder."""
    counts: Dict[str, Dict[int, Counter]] = field(default_factory=dict)
    letter_counts: Counter = field(default_factory=Counter)  # Counter per lettere A-Z
    stats: Dict[str, int] = field(default_factory=dict)


# ============================================================================
# NORMALIZZAZIONE
# ============================================================================

def strip_accents(text: str) -> str:
    """
    Rimuove accenti e diacritici dalle lettere usando Unicode NFKD.

    Args:
        text: Testo da normalizzare

    Returns:
        Testo senza accenti

    Examples:
        >>> strip_accents("perché città può")
        'perche citta puo'
    """
    # NFKD decompone caratteri composti (es. è -> e + accento)
    nfkd = unicodedata.normalize('NFKD', text)
    # Filtra solo caratteri non-diacritici
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def remove_tags(text: str) -> str:
    """
    Rimuove tag XML/HTML dal testo.

    Args:
        text: Testo con possibili tag

    Returns:
        Testo senza tag

    Examples:
        >>> remove_tags("<b>ciao</b> mondo")
        'ciao mondo'
    """
    return re.sub(r'<[^>]+>', '', text)


def normalize_to_words(
    text: str,
    alphabet: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    invalid_word_policy: str = "drop-word"
) -> List[str]:
    """
    Normalizza testo in lista di parole maiuscole, filtrando parole con caratteri non in alphabet.

    Pipeline:
    1. Rimuove tag XML/HTML
    2. Unicode NFKD
    3. Rimuove accenti
    4. Maiuscolo
    5. Estrae solo sequenze di lettere A-Z
    6. Con invalid_word_policy='drop-word', scarta parole contenenti caratteri non in alphabet

    Args:
        text: Testo grezzo
        alphabet: Alfabeto di riferimento
        invalid_word_policy: Policy per parole invalide ('drop-word' = scarta interamente)

    Returns:
        Lista di parole normalizzate (solo caratteri dell'alphabet)

    Examples:
        >>> normalize_to_words("Il gatto è nero!")
        ['IL', 'GATTO', 'E', 'NERO']
        >>> normalize_to_words("quest'inspiegabile")
        ['QUEST', 'INSPIEGABILE']
        >>> normalize_to_words("JAZZ KILO", "ABCDEFGHIKLMNOPQRSTUVWXYZ")
        ['KILO']  # JAZZ scartata perché contiene J
    """
    # Rimuove tag
    text = remove_tags(text)
    # Rimuove accenti
    text = strip_accents(text)
    # Maiuscolo
    text = text.upper()
    # Estrae solo sequenze di lettere A-Z
    words = re.findall(r'[A-Z]+', text)
    
    # Filtra parole con caratteri non in alphabet
    if invalid_word_policy == "drop-word":
        alphabet_set = set(alphabet)
        valid_words = []
        for word in words:
            # Verifica che tutti i caratteri della parola siano nell'alfabeto
            if all(char in alphabet_set for char in word):
                valid_words.append(word)
        return valid_words
    
    return words


def split_line_into_segments(
    text: str,
    mode: str,
    alphabet: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    invalid_word_policy: str = "drop-word"
) -> List[List[str]]:
    """
    Divide una riga in segmenti di parole per estrazione continuous.

    Args:
        text: Riga di testo
        mode: Modalità boundary ('sentence', 'strict', 'line', 'document')
        alphabet: Alfabeto di riferimento
        invalid_word_policy: Policy per parole invalide

    Returns:
        Lista di segmenti, ognuno dei quali è una lista di parole

    Notes:
        - sentence: resetta su punteggiatura forte, numeri, simboli
        - strict: ogni parola è un segmento isolato
        - line: ogni riga è un segmento
        - document: concatena tutto
        - Con invalid_word_policy='drop-word', parole invalide interrompono i segmenti
    """
    if mode == 'strict':
        # Ogni parola è un segmento isolato
        words = normalize_to_words(text, alphabet, invalid_word_policy)
        return [[w] for w in words]

    elif mode == 'line':
        # Tutta la riga è un segmento
        words = normalize_to_words(text, alphabet, invalid_word_policy)
        return [words] if words else []

    elif mode == 'document':
        # Tutta la riga è un segmento (come 'line' a livello riga)
        words = normalize_to_words(text, alphabet, invalid_word_policy)
        return [words] if words else []

    else:  # mode == 'sentence' (default)
        # Split su delimitatori forti
        # Delimitatori: . , ; : ! ? ( ) [ ] { } " ' / \ | - numeri
        delimiters = r'[.,;:!?()\[\]{}"\'\/\\|\-–—]|\d+'

        # Rimuove tag prima
        text = remove_tags(text)

        # Splitta su delimitatori forti
        chunks = re.split(delimiters, text)

        segments = []
        for chunk in chunks:
            words = normalize_to_words(chunk, alphabet, invalid_word_policy)
            if words:
                segments.append(words)

        return segments


# ============================================================================
# CODIFICA BASE 26
# ============================================================================

def ngram_to_id(ngram: str, alphabet: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ") -> int:
    """
    Converte n-gramma in ID intero base 26.

    Formula: id = (((c0 * 26) + c1) * 26 + c2) * 26 + ...

    Args:
        ngram: N-gramma (es. "GAT", "GATT")
        alphabet: Alfabeto di riferimento

    Returns:
        ID intero univoco per l'n-gramma

    Examples:
        >>> ngram_to_id("GAT")
        4075
        >>> ngram_to_id("GATT")
        105969
    """
    base = len(alphabet)
    idx = 0
    for char in ngram:
        pos = alphabet.index(char)
        idx = idx * base + pos
    return idx


def id_to_ngram(idx: int, n: int, alphabet: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ") -> str:
    """
    Converte ID intero in n-gramma stringa.

    Args:
        idx: ID intero
        n: Lunghezza n-gramma
        alphabet: Alfabeto di riferimento

    Returns:
        N-gramma stringa

    Examples:
        >>> id_to_ngram(4075, 3)
        'GAT'
        >>> id_to_ngram(105969, 4)
        'GATT'
    """
    base = len(alphabet)
    chars = []
    for _ in range(n):
        chars.append(alphabet[idx % base])
        idx //= base
    return ''.join(reversed(chars))


# ============================================================================
# ESTRAZIONE N-GRAMMI
# ============================================================================

def iter_ngrams_from_word(word: str, n: int) -> Iterator[str]:
    """
    Genera n-grammi da una singola parola con finestre sovrapposte.

    Args:
        word: Parola normalizzata (A-Z)
        n: Lunghezza n-gramma

    Yields:
        N-grammi

    Examples:
        >>> list(iter_ngrams_from_word("GATTO", 3))
        ['GAT', 'ATT', 'TTO']
        >>> list(iter_ngrams_from_word("GATTO", 4))
        ['GATT', 'ATTO']
    """
    for i in range(len(word) - n + 1):
        yield word[i:i+n]


def iter_ngrams_from_text(text: str, n: int) -> Iterator[str]:
    """
    Genera n-grammi da testo continuo (già normalizzato A-Z).

    Args:
        text: Testo continuo normalizzato
        n: Lunghezza n-gramma

    Yields:
        N-grammi
    """
    for i in range(len(text) - n + 1):
        yield text[i:i+n]


def count_letters(
    words: List[str],
    alphabet: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
) -> Counter:
    """
    Conta le occorrenze di ogni lettera nelle parole normalizzate.
    
    Args:
        words: Lista di parole normalizzate (solo A-Z)
        alphabet: Alfabeto di riferimento
        
    Returns:
        Counter con chiavi letter_id (0-25) e valori count
        
    Examples:
        >>> count_letters(["HELLO", "WORLD"])
        Counter({11: 3, 14: 2, 7: 1, 4: 1, 3: 1, 17: 1})  # L:3, O:2, ...
    """
    letter_counts = Counter()
    
    for word in words:
        for char in word:
            if char in alphabet:
                letter_id = alphabet.index(char)
                letter_counts[letter_id] += 1
    
    return letter_counts


def update_inword_counts(
    words: List[str],
    counts: Dict[int, Dict[int, Counter]],
    min_n: int,
    max_n: int,
    alphabet: str
) -> Tuple[int, int]:
    """
    Aggiorna contatori inword da lista di parole.

    Args:
        words: Lista di parole normalizzate
        counts: Dizionario contatori counts['inword'][n]
        min_n: Lunghezza minima n-gramma
        max_n: Lunghezza massima n-gramma
        alphabet: Alfabeto

    Returns:
        (numero_parole, numero_caratteri_totali)
    """
    total_chars = 0
    for word in words:
        total_chars += len(word)
        for n in range(min_n, max_n + 1):
            if len(word) >= n:
                for ngram in iter_ngrams_from_word(word, n):
                    ngram_id = ngram_to_id(ngram, alphabet)
                    counts['inword'][n][ngram_id] += 1
    return len(words), total_chars


def update_continuous_counts(
    segments: List[List[str]],
    counts: Dict[int, Dict[int, Counter]],
    min_n: int,
    max_n: int,
    alphabet: str
) -> int:
    """
    Aggiorna contatori continuous da segmenti.

    Args:
        segments: Lista di segmenti, ogni segmento è lista di parole
        counts: Dizionario contatori counts['continuous'][n]
        min_n: Lunghezza minima n-gramma
        max_n: Lunghezza massima n-gramma
        alphabet: Alfabeto

    Returns:
        Numero caratteri totali processati
    """
    total_chars = 0
    for segment in segments:
        # Concatena parole del segmento
        continuous_text = ''.join(segment)
        total_chars += len(continuous_text)

        # Estrae n-grammi
        for n in range(min_n, max_n + 1):
            for ngram in iter_ngrams_from_text(continuous_text, n):
                ngram_id = ngram_to_id(ngram, alphabet)
                counts['continuous'][n][ngram_id] += 1

    return total_chars


# ============================================================================
# PARSING CORPUS PAISÀ - PARALLELIZZAZIONE
# ============================================================================

def iter_paisa_text_blocks(
    corpus_file: Path,
    encoding: str = "utf-8"
) -> Iterator[str]:
    """
    Itera sui blocchi <text>...</text> del corpus PAISÀ in streaming.
    
    Args:
        corpus_file: Percorso file corpus
        encoding: Encoding file
        
    Yields:
        Contenuto testuale di ogni blocco <text> (senza tag)
        
    Notes:
        - Ignora righe che iniziano con #
        - Ignora contenuto fuori dai blocchi <text>
        - I tag <text> e </text> non sono inclusi nell'output
    """
    inside_text_block = False
    buffer = []
    
    with open(corpus_file, 'r', encoding=encoding, errors='ignore') as f:
        for line in f:
            stripped = line.strip()
            
            # Ignora commenti
            if stripped.startswith('#'):
                continue
            
            # Gestisce caso inline: <text ...>contenuto</text> sulla stessa riga
            if '<text' in line and '</text>' in line:
                # Estrae contenuto tra i tag
                line_clean = re.sub(r'<text[^>]*>', '', line)
                line_clean = re.sub(r'</text>', '', line_clean)
                if line_clean.strip():
                    yield line_clean
                continue
            
            # Apertura blocco <text>
            if '<text' in line:
                inside_text_block = True
                buffer = []
                # Rimuovi tag e aggiungi eventuale testo sulla stessa riga
                line_clean = re.sub(r'<text[^>]*>', '', line)
                if line_clean.strip():
                    buffer.append(line_clean)
                continue
            
            # Chiusura blocco </text>
            if '</text>' in line:
                # Rimuovi tag e aggiungi eventuale testo prima del tag
                line_clean = re.sub(r'</text>', '', line)
                if line_clean.strip():
                    buffer.append(line_clean)
                
                inside_text_block = False
                
                # Restituisci blocco
                if buffer:
                    yield '\n'.join(buffer)
                
                buffer = []
                continue
            
            # Aggiungi linea al buffer se siamo dentro un blocco
            if inside_text_block:
                buffer.append(line)


def batched(
    iterator: Iterator[str],
    batch_size: int
) -> Iterator[List[str]]:
    """
    Raggruppa elementi di un iteratore in batch.
    
    Args:
        iterator: Iteratore sorgente
        batch_size: Numero elementi per batch
        
    Yields:
        Liste di elementi (batch)
        
    Notes:
        - L'ultimo batch può essere più piccolo di batch_size
        - Non produce batch vuoti
    """
    batch = []
    for item in iterator:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    
    if batch:
        yield batch


def process_text_block(
    block_text: str,
    config: BuilderConfig
) -> BatchResult:
    """
    Processa un singolo blocco <text>.
    
    Args:
        block_text: Contenuto testuale del blocco
        config: Configurazione builder
        
    Returns:
        BatchResult con conteggi e statistiche del blocco
    """
    # Inizializza contatori locali
    counts = {
        'inword': {n: Counter() for n in range(config.min_n, config.max_n + 1)},
        'continuous': {n: Counter() for n in range(config.min_n, config.max_n + 1)}
    }
    
    letter_counts = Counter()
    
    stats = {
        'total_text_blocks': 1,
        'total_words': 0,
        'total_chars_inword': 0,
        'total_chars_continuous': 0
    }
    
    # Processa ogni riga del blocco
    for line in block_text.split('\n'):
        # Estrae parole normalizzate per INWORD
        words = normalize_to_words(line, config.alphabet, config.invalid_word_policy)
        if words:
            num_words, num_chars = update_inword_counts(
                words, counts, config.min_n, config.max_n, config.alphabet
            )
            stats['total_words'] += num_words
            stats['total_chars_inword'] += num_chars
            
            # Conta lettere
            line_letter_counts = count_letters(words, config.alphabet)
            letter_counts.update(line_letter_counts)
        
        # Estrae segmenti per CONTINUOUS
        segments = split_line_into_segments(
            line, config.continuous_boundary_mode, config.alphabet, config.invalid_word_policy
        )
        if segments:
            num_chars = update_continuous_counts(
                segments, counts, config.min_n, config.max_n, config.alphabet
            )
            stats['total_chars_continuous'] += num_chars
    
    return BatchResult(counts=counts, letter_counts=letter_counts, stats=stats)


def process_blocks_batch(
    blocks: List[str],
    config: BuilderConfig
) -> BatchResult:
    """
    Processa un batch di blocchi <text>.
    
    Args:
        blocks: Lista di contenuti testuali dei blocchi
        config: Configurazione builder
        
    Returns:
        BatchResult con conteggi e statistiche aggregate del batch
    """
    # Inizializza contatori aggregati
    aggregated_counts = {
        'inword': {n: Counter() for n in range(config.min_n, config.max_n + 1)},
        'continuous': {n: Counter() for n in range(config.min_n, config.max_n + 1)}
    }
    
    aggregated_letter_counts = Counter()
    
    aggregated_stats = {
        'total_text_blocks': 0,
        'total_words': 0,
        'total_chars_inword': 0,
        'total_chars_continuous': 0
    }
    
    # Processa ogni blocco e aggrega
    for block_text in blocks:
        result = process_text_block(block_text, config)
        
        # Aggrega conteggi n-grammi
        for model_type in ['inword', 'continuous']:
            for n in range(config.min_n, config.max_n + 1):
                aggregated_counts[model_type][n].update(result.counts[model_type][n])
        
        # Aggrega letter_counts
        aggregated_letter_counts.update(result.letter_counts)
        
        # Aggrega statistiche
        for key in aggregated_stats:
            aggregated_stats[key] += result.stats[key]
    
    return BatchResult(
        counts=aggregated_counts,
        letter_counts=aggregated_letter_counts,
        stats=aggregated_stats
    )


def merge_batch_result(
    global_state: BuilderState,
    batch_result: BatchResult
) -> None:
    """
    Fonde un BatchResult nello stato globale.
    
    Args:
        global_state: Stato globale da aggiornare (modificato in-place)
        batch_result: Risultato batch da fondere
    """
    # Fonde conteggi n-grammi
    for model_type in ['inword', 'continuous']:
        for n in batch_result.counts[model_type]:
            global_state.counts[model_type][n].update(batch_result.counts[model_type][n])
    
    # Fonde letter_counts
    global_state.letter_counts.update(batch_result.letter_counts)
    
    # Fonde statistiche
    for key, value in batch_result.stats.items():
        global_state.stats[key] = global_state.stats.get(key, 0) + value


def build_from_corpus_parallel(
    config: BuilderConfig
) -> BuilderState:
    """
    Costruisce modelli n-grammi dal corpus in modalità parallela.
    
    Args:
        config: Configurazione builder
        
    Returns:
        BuilderState con conteggi e statistiche finali
    """
    # Inizializza stato globale
    global_state = BuilderState(
        counts={
            'inword': {n: Counter() for n in range(config.min_n, config.max_n + 1)},
            'continuous': {n: Counter() for n in range(config.min_n, config.max_n + 1)}
        },
        stats={
            'total_lines_read': 0,
            'total_text_blocks': 0,
            'total_words': 0,
            'total_chars_inword': 0,
            'total_chars_continuous': 0,
            'total_batches_processed': 0
        }
    )
    
    # Calcola max_pending_batches
    max_pending = config.max_pending_batches
    if max_pending is None:
        max_pending = config.workers * 2
    
    if config.verbose:
        print(f"\n  Modalità parallela: {config.workers} workers", file=sys.stderr)
        print(f"  Batch size: {config.batch_size} blocchi <text>", file=sys.stderr)
        print(f"  Max pending batches: {max_pending}", file=sys.stderr)
    
    # Itera sui blocchi e crea batch
    blocks_iter = iter_paisa_text_blocks(config.corpus_file, config.encoding)
    batches_iter = batched(blocks_iter, config.batch_size)
    
    # Processa batch in parallelo
    with ProcessPoolExecutor(max_workers=config.workers) as executor:
        pending_futures = {}
        batches_submitted = 0
        
        for batch in batches_iter:
            # Attendi se troppi batch pendenti
            while len(pending_futures) >= max_pending:
                # Attendi completamento di almeno una future usando wait()
                done, pending = wait(pending_futures.keys(), return_when=FIRST_COMPLETED)
                
                # Processa future completate
                for future in done:
                    batch_result = future.result()
                    merge_batch_result(global_state, batch_result)
                    global_state.stats['total_batches_processed'] += 1
                    del pending_futures[future]
                    
                    if config.verbose and global_state.stats['total_batches_processed'] % 10 == 0:
                        print(f"  Batch processati: {global_state.stats['total_batches_processed']} | "
                              f"Blocchi <text>: {global_state.stats['total_text_blocks']:,} | "
                              f"Parole: {global_state.stats['total_words']:,}", file=sys.stderr)
            
            # Invia nuovo batch
            future = executor.submit(process_blocks_batch, batch, config)
            pending_futures[future] = batches_submitted
            batches_submitted += 1
        
        # Processa batch rimanenti
        for future in as_completed(pending_futures):
            batch_result = future.result()
            merge_batch_result(global_state, batch_result)
            global_state.stats['total_batches_processed'] += 1
            
            if config.verbose:
                print(f"  Batch processati: {global_state.stats['total_batches_processed']} | "
                      f"Blocchi <text>: {global_state.stats['total_text_blocks']:,} | "
                      f"Parole: {global_state.stats['total_words']:,}", file=sys.stderr)
    
    if config.verbose:
        print(f"\n✓ Processing parallelo completato:", file=sys.stderr)
        print(f"  Batch totali: {global_state.stats['total_batches_processed']}", file=sys.stderr)
        print(f"  Blocchi <text>: {global_state.stats['total_text_blocks']:,}", file=sys.stderr)
        print(f"  Parole estratte: {global_state.stats['total_words']:,}", file=sys.stderr)
    
    return global_state


def build_from_corpus_sequential(
    config: BuilderConfig
) -> BuilderState:
    """
    Costruisce modelli n-grammi dal corpus in modalità sequenziale.
    
    Args:
        config: Configurazione builder
        
    Returns:
        BuilderState con conteggi e statistiche finali
    """
    # Inizializza stato globale
    global_state = BuilderState(
        counts={
            'inword': {n: Counter() for n in range(config.min_n, config.max_n + 1)},
            'continuous': {n: Counter() for n in range(config.min_n, config.max_n + 1)}
        },
        letter_counts=Counter(),
        stats={
            'total_lines_read': 0,
            'total_text_blocks': 0,
            'total_words': 0,
            'total_chars_inword': 0,
            'total_chars_continuous': 0
        }
    )
    
    # Usa la funzione di parsing esistente (compatibilità)
    old_stats = parse_paisa_stream(
        corpus_file=str(config.corpus_file),
        counts=global_state.counts,
        min_n=config.min_n,
        max_n=config.max_n,
        alphabet=config.alphabet,
        invalid_word_policy=config.invalid_word_policy,
        encoding=config.encoding,
        continuous_boundary_mode=config.continuous_boundary_mode,
        progress_every=config.progress_every,
        verbose=config.verbose,
        letter_counts=global_state.letter_counts
    )
    
    # Aggiorna stats
    global_state.stats.update(old_stats)
    
    return global_state


def build_from_corpus(
    config: BuilderConfig
) -> BuilderState:
    """
    Costruisce modelli n-grammi dal corpus.
    
    Sceglie automaticamente tra modalità sequenziale e parallela
    in base al numero di workers.
    
    Args:
        config: Configurazione builder
        
    Returns:
        BuilderState con conteggi e statistiche finali
    """
    if config.workers <= 1:
        return build_from_corpus_sequential(config)
    else:
        return build_from_corpus_parallel(config)


# ============================================================================
# PARSING CORPUS PAISÀ
# ============================================================================

def parse_paisa_stream(
    corpus_file: str,
    counts: Dict[str, Dict[int, Counter]],
    min_n: int,
    max_n: int,
    alphabet: str,
    invalid_word_policy: str = "drop-word",
    encoding: str = "utf-8",
    continuous_boundary_mode: str = "sentence",
    progress_every: int = 100000,
    verbose: bool = False,
    letter_counts: Optional[Counter] = None
) -> Dict[str, Any]:
    """
    Legge corpus PAISÀ in streaming ed estrae n-grammi.

    Args:
        corpus_file: Percorso file corpus
        counts: Dizionario contatori
        min_n: Lunghezza minima n-gramma
        max_n: Lunghezza massima n-gramma
        alphabet: Alfabeto
        invalid_word_policy: Policy per parole invalide
        encoding: Encoding file
        continuous_boundary_mode: Modalità boundary continuous
        progress_every: Stampa progress ogni N righe
        verbose: Output dettagliato
        letter_counts: Counter opzionale per le lettere

    Returns:
        Dizionario con statistiche parsing
    """
    stats = {
        'total_lines_read': 0,
        'total_text_blocks': 0,
        'total_words': 0,
        'total_chars_inword': 0,
        'total_chars_continuous': 0
    }

    inside_text_block = False

    with open(corpus_file, 'r', encoding=encoding, errors='ignore') as f:
        for line in f:
            stats['total_lines_read'] += 1

            # Progress
            if verbose and stats['total_lines_read'] % progress_every == 0:
                print(f"  Linee lette: {stats['total_lines_read']:,} | "
                      f"Blocchi <text>: {stats['total_text_blocks']:,} | "
                      f"Parole: {stats['total_words']:,}", file=sys.stderr)

            line = line.strip()

            # Ignora commenti
            if line.startswith('#'):
                continue

            # Apertura blocco <text>
            if '<text' in line:
                stats['total_text_blocks'] += 1
                # Rimuove il tag dall'inizio della riga
                line = re.sub(r'<text[^>]*>', '', line)
                inside_text_block = True
            
            # Chiusura blocco </text>
            if '</text>' in line:
                # Processa eventuale testo prima del tag
                line = re.sub(r'</text>', '', line)
                # Processa il testo rimanente se siamo dentro un blocco
                # poi chiudi il blocco
                needs_processing = inside_text_block and line.strip()
                inside_text_block = False
                
                if not needs_processing:
                    continue
            elif not inside_text_block:
                # Se non siamo in un blocco e non c'è </text>, skip
                continue
            
            # A questo punto abbiamo testo da processare
            if not line.strip():
                continue

            # Estrae parole normalizzate per INWORD
            words = normalize_to_words(line, alphabet, invalid_word_policy)
            if words:
                num_words, num_chars = update_inword_counts(
                    words, counts, min_n, max_n, alphabet
                )
                stats['total_words'] += num_words
                stats['total_chars_inword'] += num_chars
                
                # Conta lettere se richiesto
                if letter_counts is not None:
                    line_letter_counts = count_letters(words, alphabet)
                    letter_counts.update(line_letter_counts)

            # Estrae segmenti per CONTINUOUS
            segments = split_line_into_segments(line, continuous_boundary_mode, alphabet, invalid_word_policy)
            if segments:
                num_chars = update_continuous_counts(
                    segments, counts, min_n, max_n, alphabet
                )
                stats['total_chars_continuous'] += num_chars

    if verbose:
        print(f"\n✓ Parsing completato:", file=sys.stderr)
        print(f"  Righe totali: {stats['total_lines_read']:,}", file=sys.stderr)
        print(f"  Blocchi <text>: {stats['total_text_blocks']:,}", file=sys.stderr)
        print(f"  Parole estratte: {stats['total_words']:,}", file=sys.stderr)

    return stats


# ============================================================================
# PROBABILITÀ E SMOOTHING
# ============================================================================

def build_probability_arrays(
    counts: Dict[str, Dict[int, Counter]],
    alphabet: str,
    alpha: float,
    verbose: bool,
    need_arrays: bool = True
) -> Dict[str, Dict[int, Dict[str, Any]]]:
    """
    Costruisce array di probabilità e statistiche.
    
    Args:
        counts: Contatori n-grammi
        alphabet: Alfabeto
        alpha: Parametro smoothing
        verbose: Output dettagliato
        need_arrays: Se True, crea array NumPy (richiede numpy)
        
    Returns:
        Dizionario con modelli e statistiche
    """
    base = len(alphabet)
    models = {}
    
    # Import numpy solo se necessario
    if need_arrays:
        import numpy as np
    
    for model_type in ['inword', 'continuous']:
        models[model_type] = {}
        
        for n in counts[model_type]:
            vocab_size = base ** n
            counter = counts[model_type][n]
            
            # Statistiche
            total_ngrams = sum(counter.values())
            unique_ngrams = len(counter)
            
            # Default log probability per n-grammi non osservati
            default_log_prob = math.log(alpha / (total_ngrams + alpha * vocab_size))
            
            if verbose:
                print(f"\n  Modello {n}-grammi {model_type}:", file=sys.stderr)
                print(f"    Total n-grams: {total_ngrams:,}", file=sys.stderr)
                print(f"    Unique n-grams: {unique_ngrams:,}", file=sys.stderr)
                print(f"    Vocab size: {vocab_size:,}", file=sys.stderr)
                print(f"    Default log prob: {default_log_prob:.6f}", file=sys.stderr)
            
            # Inizializza array con valori default (solo se richiesto)
            if need_arrays:
                logprob_array = np.full(vocab_size, default_log_prob, dtype=np.float32)
                counts_array = np.zeros(vocab_size, dtype=np.uint64)
            else:
                logprob_array = None
                counts_array = None

            # Lista per CSV (solo n-grammi osservati)
            csv_data = []

            # Popola array e lista CSV
            for ngram_id, count in counter.items():
                # Probabilità grezza
                probability = count / total_ngrams
                
                # Smoothed probability
                smoothed_prob = (count + alpha) / (total_ngrams + alpha * vocab_size)
                
                # Log probability
                log_prob = math.log(smoothed_prob)
                
                # Aggiorna array (solo se richiesto)
                if need_arrays:
                    logprob_array[ngram_id] = log_prob
                    counts_array[ngram_id] = count
                
                # Aggiungi a CSV data
                ngram_str = id_to_ngram(ngram_id, n, alphabet)
                csv_data.append({
                    'ngram_id': ngram_id,
                    'ngram': ngram_str,
                    'count': count,
                    'probability': probability,
                    'smoothed_probability': smoothed_prob,
                    'log_probability': log_prob
                })

            # Ordina per count decrescente e assegna rank
            csv_data.sort(key=lambda x: x['count'], reverse=True)
            for rank, item in enumerate(csv_data, 1):
                item['rank'] = rank

            # Salva nel modello
            models[model_type][n] = {
                'total_ngrams': total_ngrams,
                'unique_ngrams': unique_ngrams,
                'vocab_size': vocab_size,
                'default_log_probability': default_log_prob,
                'logprob_array': logprob_array,
                'counts_array': counts_array,
                'csv_data': csv_data
            }

    return models


# ============================================================================
# OUTPUT
# ============================================================================

def write_csv(
    csv_data: List[Dict[str, Any]],
    output_file: str,
    n: int,
    model_type: str,
    min_count: int,
    verbose: bool
) -> None:
    """
    Scrive file CSV con n-grammi.

    Args:
        csv_data: Lista di dizionari con dati n-grammi
        output_file: Percorso file output
        n: Lunghezza n-gramma
        model_type: Tipo modello ('inword' o 'continuous')
        min_count: Count minimo per includere n-gramma
        verbose: Output dettagliato
    """
    import csv

    # Filtra per min_count
    filtered_data = [item for item in csv_data if item['count'] >= min_count]

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'ngram', 'ngram_id', 'n', 'model',
            'count', 'probability', 'smoothed_probability',
            'log_probability', 'rank'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for item in filtered_data:
            writer.writerow({
                'ngram': item['ngram'],
                'ngram_id': item['ngram_id'],
                'n': n,
                'model': model_type,
                'count': item['count'],
                'probability': f"{item['probability']:.10f}",
                'smoothed_probability': f"{item['smoothed_probability']:.10f}",
                'log_probability': f"{item['log_probability']:.6f}",
                'rank': item['rank']
            })

    if verbose:
        print(f"  ✓ CSV salvato: {output_file} ({len(filtered_data):,} n-grammi)", file=sys.stderr)


def write_npy(
    logprob_array,
    counts_array,
    logprob_file: str,
    counts_file: str,
    verbose: bool
) -> None:
    """
    Scrive array NPY.

    Args:
        logprob_array: Array log probability
        counts_array: Array counts
        logprob_file: File output log probability
        counts_file: File output counts
        verbose: Output dettagliato
    """
    import numpy as np

    np.save(logprob_file, logprob_array)
    np.save(counts_file, counts_array)

    if verbose:
        print(f"  ✓ NPY salvati: {logprob_file}, {counts_file}", file=sys.stderr)


def write_letter_csv(
    letter_counts: Counter,
    alpha_letters: float,
    output_file: str,
    alphabet: str,
    verbose: bool
) -> None:
    """
    Scrive file CSV con frequenze lettere.
    
    Args:
        letter_counts: Counter con letter_id -> count
        alpha_letters: Parametro smoothing per lettere
        output_file: Percorso file output
        alphabet: Alfabeto
        verbose: Output dettagliato
    """
    import csv
    
    # Calcola totale lettere
    total_letters = sum(letter_counts.values())
    
    if total_letters == 0:
        if verbose:
            print(f"  ⚠ Nessuna lettera da salvare", file=sys.stderr)
        return
    
    # Prepara dati
    csv_data = []
    for letter_id in range(len(alphabet)):
        letter = alphabet[letter_id]
        count = letter_counts.get(letter_id, 0)
        frequency = count / total_letters
        smoothed_frequency = (count + alpha_letters) / (total_letters + alpha_letters * len(alphabet))
        log_probability = math.log(smoothed_frequency)
        
        csv_data.append({
            'letter': letter,
            'letter_id': letter_id,
            'count': count,
            'frequency': frequency,
            'smoothed_frequency': smoothed_frequency,
            'log_probability': log_probability
        })
    
    # Ordina per count decrescente, poi letter_id crescente
    csv_data.sort(key=lambda x: (-x['count'], x['letter_id']))
    
    # Aggiungi rank
    for rank, item in enumerate(csv_data, 1):
        item['rank'] = rank
    
    # Scrivi CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'letter', 'letter_id', 'count', 'frequency',
            'smoothed_frequency', 'log_probability', 'rank'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for item in csv_data:
            writer.writerow({
                'letter': item['letter'],
                'letter_id': item['letter_id'],
                'count': item['count'],
                'frequency': f"{item['frequency']:.10f}",
                'smoothed_frequency': f"{item['smoothed_frequency']:.10f}",
                'log_probability': f"{item['log_probability']:.6f}",
                'rank': item['rank']
            })
    
    if verbose:
        print(f"  ✓ Letter CSV salvato: {output_file} ({len(alphabet)} lettere)", file=sys.stderr)


def write_letter_npy(
    letter_counts: Counter,
    alpha_letters: float,
    counts_file: str,
    frequencies_file: str,
    logprob_file: str,
    alphabet: str,
    verbose: bool
) -> None:
    """
    Scrive array NPY per le frequenze lettere.
    
    Args:
        letter_counts: Counter con letter_id -> count
        alpha_letters: Parametro smoothing
        counts_file: File output counts
        frequencies_file: File output frequencies
        logprob_file: File output log probabilities
        alphabet: Alfabeto
        verbose: Output dettagliato
    """
    import numpy as np
    
    vocab_size = len(alphabet)
    total_letters = sum(letter_counts.values())
    
    # Inizializza array
    counts_array = np.zeros(vocab_size, dtype=np.int64)
    frequencies_array = np.zeros(vocab_size, dtype=np.float32)
    logprob_array = np.zeros(vocab_size, dtype=np.float32)
    
    # Riempi array
    for letter_id in range(vocab_size):
        count = letter_counts.get(letter_id, 0)
        counts_array[letter_id] = count
        
        if total_letters > 0:
            frequency = count / total_letters
            smoothed_frequency = (count + alpha_letters) / (total_letters + alpha_letters * vocab_size)
        else:
            frequency = 0.0
            smoothed_frequency = 1.0 / vocab_size
        
        frequencies_array[letter_id] = frequency
        logprob_array[letter_id] = math.log(smoothed_frequency)
    
    # Salva array
    np.save(counts_file, counts_array)
    np.save(frequencies_file, frequencies_array)
    np.save(logprob_file, logprob_array)
    
    if verbose:
        print(f"  ✓ Letter NPY salvati: {counts_file}, {frequencies_file}, {logprob_file}", file=sys.stderr)


def write_metadata(
    metadata: Dict[str, Any],
    output_file: str,
    verbose: bool
) -> None:
    """
    Scrive file metadata.json.

    Args:
        metadata: Dizionario metadata
        output_file: File output
        verbose: Output dettagliato
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    if verbose:
        print(f"  ✓ Metadata salvato: {output_file}", file=sys.stderr)


def write_generated_model_readme(
    metadata: Dict[str, Any],
    output_file: str,
    verbose: bool
) -> None:
    """
    Genera README_GENERATED_MODEL.md automaticamente.
    
    Args:
        metadata: Dizionario metadata
        output_file: File output
        verbose: Output dettagliato
    """
    # Estrai valori usati frequentemente
    base_value = metadata.get('base', 26)
    
    # Informazioni sulla modalità di esecuzione
    execution_info = ""
    if metadata.get('execution_mode') == 'parallel':
        execution_info = f"""
## 2.5. Modalità di esecuzione

Questo modello è stato generato in **modalità parallela** utilizzando **{metadata.get('workers', 'N/A')} worker**.

- **Batch size**: {metadata.get('batch_size', 'N/A')} blocchi `<text>` per batch
- **Total batches**: {metadata['stats'].get('total_batches_processed', 'N/A')}

**Garanzie di correttezza**:
- Ogni blocco `<text>...</text>` è stato trattato come documento indipendente
- Il buffer continuous è stato resettato alla fine di ogni blocco
- **Nessun n-gramma continuous attraversa due blocchi diversi**
- I risultati sono identici alla modalità sequenziale
"""
    else:
        execution_info = f"""
## 2.5. Modalità di esecuzione

Questo modello è stato generato in **modalità sequenziale** (single-threaded).
"""
    
    content = f"""# Modello n-grammi PAISÀ generato

**Data generazione**: {metadata.get('generation_date', 'N/A')}

## 1. Scopo

Questo modello statistico è stato generato per lo **scoring crittoanalitico di plaintext candidati** 
durante attacchi al cifrario di Vigenère Playfair.

I modelli n-grammi permettono di valutare se una sequenza decrittata assomiglia 
statisticamente all'italiano, aiutando a identificare la chiave corretta.

## 2. Corpus sorgente

- **Nome corpus**: {metadata.get('corpus', 'N/A')}
- **File sorgente**: `{metadata.get('corpus_file', 'N/A')}`
- **Righe lette**: {metadata['stats'].get('total_lines_read', 0):,}
- **Blocchi `<text>` processati**: {metadata['stats'].get('total_text_blocks', 0):,}
- **Parole estratte**: {metadata['stats'].get('total_words', 0):,}
- **Directory output**: `{metadata.get('output_dir', 'N/A')}`
{execution_info}
## 3. Normalizzazione applicata

Il testo è stato normalizzato seguendo queste regole:

- **Unicode NFKD**: decomposizione caratteri composti
- **Accenti rimossi**: lettere accentate convertite in lettere semplici
  - à á â ä ã å → A
  - è é ê ë → E
  - ì í î ï → I
  - ò ó ô ö õ → O
  - ù ú û ü → U
  - ç → C
- **Maiuscolo**: tutte lettere convertite in maiuscolo
- **Alfabeto**: `{metadata.get('alphabet', 'N/A')}` (base {metadata.get('base', 'N/A')})
- **Invalid word policy**: `{metadata.get('invalid_word_policy', 'N/A')}`
  - Con policy `drop-word`, le parole contenenti caratteri non presenti nell'alfabeto vengono **scartate interamente**
  - Le parole scartate **interrompono** i segmenti continuous (non vengono mai convertite o modificate)
- **Tag XML/HTML rimossi**: `<tag>` rimossi, contenuto conservato
- **Righe commento ignorate**: righe che iniziano con `#`
- **Reset sui blocchi**: buffer continuous resettato a ogni `</text>`

**Modalità boundary continuous**: `{metadata.get('continuous_boundary_mode', 'N/A')}`

## 4. Modelli generati

Sono stati generati **quattro modelli statistici** distinti:

### 4.1. Trigrammi INWORD

N-grammi estratti **solo dentro singole parole**.

- Total n-grams: {metadata['models']['3_inword'].get('total_ngrams', 0):,}
- Unique n-grams: {metadata['models']['3_inword'].get('unique_ngrams', 0):,}
- Vocab size: {metadata['models']['3_inword'].get('vocab_size', 0):,}
- Default log probability: {metadata['models']['3_inword'].get('default_log_probability', 0):.6f}
- CSV: `{metadata['models']['3_inword'].get('csv_file', 'N/A')}`
- NPY logprob: `{metadata['models']['3_inword'].get('logprob_npy_file', 'N/A')}`
- NPY counts: `{metadata['models']['3_inword'].get('counts_npy_file', 'N/A')}`

### 4.2. Quadrigrammi INWORD

N-grammi estratti **solo dentro singole parole**.

- Total n-grams: {metadata['models']['4_inword'].get('total_ngrams', 0):,}
- Unique n-grams: {metadata['models']['4_inword'].get('unique_ngrams', 0):,}
- Vocab size: {metadata['models']['4_inword'].get('vocab_size', 0):,}
- Default log probability: {metadata['models']['4_inword'].get('default_log_probability', 0):.6f}
- CSV: `{metadata['models']['4_inword'].get('csv_file', 'N/A')}`
- NPY logprob: `{metadata['models']['4_inword'].get('logprob_npy_file', 'N/A')}`
- NPY counts: `{metadata['models']['4_inword'].get('counts_npy_file', 'N/A')}`

### 4.3. Trigrammi CONTINUOUS

N-grammi estratti da **segmenti testuali concatenati**, possono attraversare spazi tra parole 
ma non delimitatori forti.

- Total n-grams: {metadata['models']['3_continuous'].get('total_ngrams', 0):,}
- Unique n-grams: {metadata['models']['3_continuous'].get('unique_ngrams', 0):,}
- Vocab size: {metadata['models']['3_continuous'].get('vocab_size', 0):,}
- Default log probability: {metadata['models']['3_continuous'].get('default_log_probability', 0):.6f}
- CSV: `{metadata['models']['3_continuous'].get('csv_file', 'N/A')}`
- NPY logprob: `{metadata['models']['3_continuous'].get('logprob_npy_file', 'N/A')}`
- NPY counts: `{metadata['models']['3_continuous'].get('counts_npy_file', 'N/A')}`

### 4.4. Quadrigrammi CONTINUOUS

N-grammi estratti da **segmenti testuali concatenati**, possono attraversare spazi tra parole 
ma non delimitatori forti.

- Total n-grams: {metadata['models']['4_continuous'].get('total_ngrams', 0):,}
- Unique n-grams: {metadata['models']['4_continuous'].get('unique_ngrams', 0):,}
- Vocab size: {metadata['models']['4_continuous'].get('vocab_size', 0):,}
- Default log probability: {metadata['models']['4_continuous'].get('default_log_probability', 0):.6f}
- CSV: `{metadata['models']['4_continuous'].get('csv_file', 'N/A')}`
- NPY logprob: `{metadata['models']['4_continuous'].get('logprob_npy_file', 'N/A')}`
- NPY counts: `{metadata['models']['4_continuous'].get('counts_npy_file', 'N/A')}`

## 5. Formato CSV

Ogni file CSV rappresenta un modello statistico n-gram distinto e contiene le seguenti colonne:

1. **ngram**: Rappresentazione testuale dell'n-gramma (es. "GAT", "GATT")
2. **ngram_id**: ID intero base {metadata.get('base', 26)} dell'n-gramma
3. **n**: Lunghezza n-gramma (3 o 4)
4. **model**: Tipo modello (`inword` o `continuous`)
5. **count**: Numero occorrenze osservate nel corpus
6. **probability**: Probabilità grezza (count / total_ngrams)
7. **smoothed_probability**: Probabilità con smoothing additivo
8. **log_probability**: Logaritmo naturale della smoothed_probability (da usare per scoring)
9. **rank**: Posizione n-gramma ordinato per count decrescente

**Nota**: I CSV contengono solo n-grammi osservati con `count >= min_count`.

## 6. Formato NPY

Per ogni modello vengono generati due array NumPy:

### 6.1. `*_logprob.npy`

Array monodimensionale di tipo `float32`.

- **Dimensione**: {metadata.get('base', 26)}^n (trigrammi: {metadata.get('base', 26)**3:,}, quadrigrammi: {metadata.get('base', 26)**4:,})
- **Indice**: ngram_id
- **Valore**: log_probability dell'n-gramma
- **N-grammi non osservati**: contengono `default_log_probability`

### 6.2. `*_counts.npy`

Array monodimensionale di tipo `uint64`.

- **Dimensione**: {metadata.get('base', 26)}^n
- **Indice**: ngram_id  
- **Valore**: count osservato
- **N-grammi non osservati**: valore 0

## 7. Codifica base {base_value}

Ogni n-gramma è rappresentato come intero usando codifica base {base_value}.

**Alfabeto**: `{metadata.get('alphabet', 'N/A')}`

**Mappatura**: Ogni carattere dell'alfabeto ha un indice da 0 a {base_value - 1}

**Formula**: `id = (((c0 * base) + c1) * base + c2) * base + ...`

La codifica è **biunivoca** per n fissato e non produce collisioni.

## 8. Smoothing e alpha

Per evitare probabilità zero per n-grammi non osservati, viene applicato **smoothing additivo**.

**Parametro alpha**: `{metadata.get('alpha', 'N/A')}`

**Formula smoothed probability**:
```
smoothed_probability = (count + alpha) / (total_ngrams + alpha * vocab_size)
```

**Formula default log probability** (per n-grammi non osservati):
```
default_log_probability = ln(alpha / (total_ngrams + alpha * vocab_size))
```

**Interpretazione**:
- Alpha basso: modello più severo
- Alpha alto: modello più permissivo
- Valore tipico per italiano: 0.01

## 9. Frequenze delle lettere

Oltre ai modelli n-grammi, sono state generate le **frequenze statistiche delle singole lettere** dell'alfabeto.

**Perché sono utili**: Le frequenze lettere permettono di:
- Valutare la plausibilità delle singole colonne nel Vigenère dopo lo split per lunghezza chiave
- Stimare i migliori shift Caesar per ogni colonna usando chi-square
- Calcolare score monogramma/log-likelihood sul plaintext candidato
- Affiancare gli score a trigrammi/quadrigrammi nel ranking finale

**Normalizzazione**: Le lettere sono state contate usando la stessa normalizzazione degli n-grammi e la stessa policy drop-word.

### 9.1. Statistiche lettere

- **Total letters**: {metadata['letters'].get('total_letters', 0):,}
- **Unique letters**: {metadata['letters'].get('unique_letters', 0)}
- **Alphabet size**: {metadata.get('base', 26)}
- **Alpha letters**: {metadata['letters'].get('alpha_letters', 0.01)}

### 9.2. Top lettere più frequenti

{''.join([f"- **{item['letter']}**: count={item['count']:,}, frequency={item['frequency']:.6f}, rank={item['rank']}\n" for item in metadata['letters'].get('top_letters', [])])}

### 9.3. File generati

- **CSV**: `{metadata['letters'].get('csv_file', 'N/A')}`
- **NPY counts**: `{metadata['letters'].get('counts_npy_file', 'N/A')}`
- **NPY frequencies**: `{metadata['letters'].get('frequencies_npy_file', 'N/A')}`
- **NPY logprob**: `{metadata['letters'].get('logprob_npy_file', 'N/A')}`

### 9.4. Formato CSV lettere

Colonne:
1. **letter**: Lettera dell'alfabeto
2. **letter_id**: ID intero (0 a {metadata.get('base', 26) - 1})
3. **count**: Numero occorrenze osservate
4. **frequency**: Frequenza grezza (count / total_letters)
5. **smoothed_frequency**: Frequenza con smoothing
6. **log_probability**: Logaritmo naturale della smoothed_frequency
7. **rank**: Posizione ordinata per count decrescente

### 9.5. Formato NPY lettere

Tre array monodimensionali di lunghezza {metadata.get('base', 26)}:

- **`paisa_letter_counts.npy`**: Array `int64`, indicizzato da letter_id, contiene count
- **`paisa_letter_frequencies.npy`**: Array `float32`, contiene frequency grezza
- **`paisa_letter_logprob.npy`**: Array `float32`, contiene log_probability smoothed (da usare per scoring)

### 9.6. Esempio uso: Score monogramma

```python
import numpy as np

# Carica log probability lettere
letter_logprob = np.load("npy/paisa_letter_logprob.npy")

def score_letters(plain_nums):
    \"\"\"Score monogramma di un plaintext.\"\"\"
    total = 0.0
    for x in plain_nums:
        total += float(letter_logprob[x])
    return total / max(1, len(plain_nums))

# Esempio
plaintext = "ILGATTO"
plain_nums = [ord(c) - ord('A') for c in plaintext]
score = score_letters(plain_nums)
print(f"Score monogramma: {{score:.6f}}")
```

### 9.7. Esempio uso: Chi-square per colonna Vigenère

```python
import numpy as np

# Carica frequenze attese italiane
letter_freq = np.load("npy/paisa_letter_frequencies.npy")

def chi_square_column(column_nums, expected_freq):
    \"\"\"
    Calcola chi-square tra distribuzione osservata e attesa.
    Valori più bassi = migliore match.
    \"\"\"
    observed = [0] * 26
    for x in column_nums:
        observed[x] += 1
    
    n = len(column_nums)
    chi2 = 0.0
    
    for i in range(26):
        expected = expected_freq[i] * n
        if expected > 0:
            chi2 += ((observed[i] - expected) ** 2) / expected
    
    return chi2

# Per ogni shift Caesar (0-25), calcola chi-square della colonna decifrata
# Lo shift con chi-square minimo è il candidato migliore
```

**Nota**: Le frequenze lettere affiancano trigrammi/quadrigrammi, non li sostituiscono. 
Per Vigenère, i quadrigrammi sono più discriminanti, le lettere servono come filtro robusto iniziale.

## 10. Esempio di caricamento Python

```python
import numpy as np

# Carica array log probability
quad_continuous = np.load("npy/paisa_4grams_continuous_logprob.npy")
quad_inword = np.load("npy/paisa_4grams_inword_logprob.npy")

# Funzione codifica base 26
def ngram_to_id(ngram, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    idx = 0
    for char in ngram:
        idx = idx * 26 + alphabet.index(char)
    return idx

# Recupera score di un n-gramma
ngram = "GATT"
ngram_id = ngram_to_id(ngram)
score = quad_continuous[ngram_id]
print(f"Score {{ngram}}: {{score:.6f}}")
```

## 11. Esempio di scoring Vigenère

```python
import numpy as np

# Carica modello
quad_scores = np.load("npy/paisa_4grams_continuous_logprob.npy")

def score_quadgrams(plain_nums, quad_scores):
    \"\"\"
    Calcola score medio di un plaintext candidato.
    
    Args:
        plain_nums: plaintext come lista di interi 0..25
        quad_scores: array log probability quadrigrammi
        
    Returns:
        Score medio logaritmico
    \"\"\"
    total = 0.0
    count = 0
    
    for i in range(len(plain_nums) - 3):
        a = plain_nums[i]
        b = plain_nums[i + 1]
        c = plain_nums[i + 2]
        d = plain_nums[i + 3]
        
        # Calcola ngram_id base 26
        idx = (((a * 26) + b) * 26 + c) * 26 + d
        
        # Accumula score
        total += float(quad_scores[idx])
        count += 1
    
    # Restituisce score medio
    return total / max(1, count)

# Esempio uso
plaintext = "ILGATTONERODORME"
plain_nums = [ord(c) - ord('A') for c in plaintext]
score = score_quadgrams(plain_nums, quad_scores)
print(f"Score plaintext: {{score:.6f}}")
```

## 12. Avvertenze

- **CSV vs NPY**: 
  - I CSV contengono solo n-grammi osservati (più compatti, per audit umano)
  - Gli NPY contengono tutti i 26^n ID possibili (più veloci per scoring automatico)

- **Normalizzazione coerente**:
  - I modelli sono validi solo per testi normalizzati A-Z maiuscolo
  - Applicare la stessa normalizzazione ai plaintext candidati

- **Modelli complementari**:
  - INWORD e CONTINUOUS misurano aspetti linguistici diversi
  - Possono essere combinati con pesi diversi nello scoring finale

- **Comparabilità**:
  - Non confrontare score prodotti con alpha diversi
  - Non confrontare score prodotti da corpus diversi
  - Usare solo per confronto relativo tra candidati

- **Performance**:
  - Array NPY permettono lookup O(1) per scoring
  - Preferire NPY per scoring massivo di candidati

## 13. File generati

```
{metadata.get('output_dir', 'N/A')}/
├── metadata.json
├── README_GENERATED_MODEL.md
├── csv/
│   ├── paisa_3grams_inword.csv
│   ├── paisa_4grams_inword.csv
│   ├── paisa_3grams_continuous.csv
│   └── paisa_4grams_continuous.csv
└── npy/
    ├── paisa_3grams_inword_logprob.npy
    ├── paisa_4grams_inword_logprob.npy
    ├── paisa_3grams_continuous_logprob.npy
    ├── paisa_4grams_continuous_logprob.npy
    ├── paisa_3grams_inword_counts.npy
    ├── paisa_4grams_inword_counts.npy
    ├── paisa_3grams_continuous_counts.npy
    └── paisa_4grams_continuous_counts.npy
```

---

*Generato automaticamente da `build_paisa_ngrams.py`*
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

    if verbose:
        print(f"  ✓ README generato: {output_file}", file=sys.stderr)


# ============================================================================
# SELF TEST
# ============================================================================

def run_self_test() -> int:
    """
    Esegue test interni rapidi.

    Returns:
        Exit code (0 = successo, 1 = fallimento)
    """
    print("=== SELF TEST ===\n", file=sys.stderr)

    # Test normalizzazione
    print("Test normalizzazione...", file=sys.stderr)
    assert normalize_to_words("perché") == ["PERCHE"]
    assert normalize_to_words("città") == ["CITTA"]
    assert normalize_to_words("può più così") == ["PUO", "PIU", "COSI"]
    assert normalize_to_words("E' fondamentale") == ["E", "FONDAMENTALE"]
    assert normalize_to_words("quest'inspiegabile") == ["QUEST", "INSPIEGABILE"]
    assert normalize_to_words("larghezza 1/8\"") == ["LARGHEZZA"]
    assert normalize_to_words("<b>ciao</b>") == ["CIAO"]
    print("  ✓ Normalizzazione OK", file=sys.stderr)

    # Test codifica base 26
    print("Test codifica base 26...", file=sys.stderr)
    assert ngram_to_id("A") == 0
    assert ngram_to_id("B") == 1
    assert ngram_to_id("Z") == 25
    assert ngram_to_id("AA") == 0
    assert ngram_to_id("AB") == 1
    assert ngram_to_id("AZ") == 25
    assert ngram_to_id("BA") == 26
    assert ngram_to_id("GAT") == 4075
    assert ngram_to_id("GATT") == 105969
    assert id_to_ngram(ngram_to_id("GATT"), 4) == "GATT"
    assert id_to_ngram(ngram_to_id("IONE"), 4) == "IONE"
    assert id_to_ngram(ngram_to_id("AAA"), 3) == "AAA"
    assert id_to_ngram(ngram_to_id("ZZZ"), 3) == "ZZZ"
    print("  ✓ Codifica base 26 OK", file=sys.stderr)

    # Test estrazione n-grammi
    print("Test estrazione n-grammi...", file=sys.stderr)
    assert list(iter_ngrams_from_word("GATTO", 3)) == ["GAT", "ATT", "TTO"]
    assert list(iter_ngrams_from_word("GATTO", 4)) == ["GATT", "ATTO"]
    print("  ✓ Estrazione n-grammi OK", file=sys.stderr)

    # Test collisioni trigrammi
    print("Test collisioni trigrammi...", file=sys.stderr)
    seen_ids = set()
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i in range(26):
        for j in range(26):
            for k in range(26):
                ngram = alphabet[i] + alphabet[j] + alphabet[k]
                ngram_id = ngram_to_id(ngram)
                assert ngram_id not in seen_ids, f"Collision for {ngram}: {ngram_id}"
                seen_ids.add(ngram_id)
    assert len(seen_ids) == 26**3
    print("  ✓ Nessuna collisione trigrammi OK", file=sys.stderr)

    print("\n=== TUTTI I TEST PASSATI ===\n", file=sys.stderr)
    return 0


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Costruisce modelli n-grammi dal corpus PAISÀ per crittoanalisi Vigenère",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--corpus-file',
        type=str,
        required=False,
        help='Percorso al file corpus PAISÀ'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='./assets/ngrams_paisa',
        help='Directory output (default: ./assets/ngrams_paisa)'
    )

    parser.add_argument(
        '--min-n',
        type=int,
        default=3,
        help='Lunghezza minima n-gramma (default: 3)'
    )

    parser.add_argument(
        '--max-n',
        type=int,
        default=4,
        help='Lunghezza massima n-gramma (default: 4)'
    )

    parser.add_argument(
        '--alphabet',
        type=str,
        default='ABCDEFGHIJKLMNOPQRSTUVWXYZ',
        help='Alfabeto (default: A-Z)'
    )

    parser.add_argument(
        '--invalid-word-policy',
        type=str,
        choices=['drop-word'],
        default='drop-word',
        help='Policy per parole con caratteri non in alphabet (default: drop-word)'
    )

    parser.add_argument(
        '--alpha',
        type=float,
        default=0.01,
        help='Parametro smoothing (default: 0.01)'
    )

    parser.add_argument(
        '--alpha-letters',
        type=float,
        default=None,
        help='Parametro smoothing per lettere (default: usa --alpha)'
    )

    parser.add_argument(
        '--min-count',
        type=int,
        default=1,
        help='Count minimo per CSV (default: 1)'
    )

    parser.add_argument(
        '--encoding',
        type=str,
        default='utf-8',
        help='Encoding file corpus (default: utf-8)'
    )

    parser.add_argument(
        '--progress-every',
        type=int,
        default=100000,
        help='Stampa progress ogni N righe (default: 100000)'
    )

    parser.add_argument(
        '--continuous-boundary-mode',
        type=str,
        choices=['sentence', 'strict', 'line', 'document'],
        default='sentence',
        help='Modalità boundary continuous (default: sentence)'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=1,
        help='Numero di worker paralleli (default: 1 = sequenziale)'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Numero di blocchi <text> per batch (default: 1000)'
    )
    
    parser.add_argument(
        '--max-pending-batches',
        type=int,
        default=None,
        help='Massimo numero di batch pendenti (default: workers * 2)'
    )
    
    parser.add_argument(
        '--save-csv',
        action='store_true',
        help='Salva file CSV'
    )

    parser.add_argument(
        '--save-npy',
        action='store_true',
        help='Salva file NPY'
    )

    parser.add_argument(
        '--self-test',
        action='store_true',
        help='Esegue test interni e termina'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Output dettagliato'
    )

    args = parser.parse_args()

    # Self test
    if args.self_test:
        sys.exit(run_self_test())

    # Validazione argomenti
    if not args.corpus_file:
        print("Errore: --corpus-file richiesto (oppure usa --self-test)", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.corpus_file):
        print(f"Errore: File corpus non trovato: {args.corpus_file}", file=sys.stderr)
        sys.exit(1)

    if not args.save_csv and not args.save_npy:
        print("Avviso: Nessun output richiesto (usa --save-csv e/o --save-npy)", file=sys.stderr)
        print("Procedo comunque con analisi...", file=sys.stderr)

    # Importa numpy solo se necessario
    if args.save_npy:
        try:
            import numpy as np
        except ImportError:
            print("Errore: numpy richiesto per --save-npy", file=sys.stderr)
            print("Installa con: pip install numpy", file=sys.stderr)
            sys.exit(1)

    # Crea directory output
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_dir = output_dir / 'csv'
    npy_dir = output_dir / 'npy'

    if args.save_csv:
        csv_dir.mkdir(exist_ok=True)

    if args.save_npy:
        npy_dir.mkdir(exist_ok=True)

    print(f"\n{'='*70}", file=sys.stderr)
    print(f"N-GRAM BUILDER - Corpus PAISÀ", file=sys.stderr)
    print(f"{'='*70}\n", file=sys.stderr)
    
    # Crea configurazione
    config = BuilderConfig(
        corpus_file=Path(args.corpus_file),
        output_dir=output_dir,
        min_n=args.min_n,
        max_n=args.max_n,
        alphabet=args.alphabet,
        invalid_word_policy=args.invalid_word_policy,
        alpha=args.alpha,
        alpha_letters=args.alpha_letters if args.alpha_letters is not None else args.alpha,
        min_count=args.min_count,
        encoding=args.encoding,
        continuous_boundary_mode=args.continuous_boundary_mode,
        save_csv=args.save_csv,
        save_npy=args.save_npy,
        workers=args.workers,
        batch_size=args.batch_size,
        max_pending_batches=args.max_pending_batches,
        progress_every=args.progress_every,
        verbose=args.verbose
    )
    
    if args.verbose:
        print(f"Parametri:", file=sys.stderr)
        print(f"  Corpus: {args.corpus_file}", file=sys.stderr)
        print(f"  Output: {args.output_dir}", file=sys.stderr)
        print(f"  N-grammi: {args.min_n}-{args.max_n}", file=sys.stderr)
        print(f"  Alfabeto: {args.alphabet} (base {len(args.alphabet)})", file=sys.stderr)
        print(f"  Alpha: {args.alpha}", file=sys.stderr)
        print(f"  Min count CSV: {args.min_count}", file=sys.stderr)
        print(f"  Boundary mode: {args.continuous_boundary_mode}", file=sys.stderr)
        print(f"  Workers: {args.workers}", file=sys.stderr)
        print(f"  Batch size: {args.batch_size}", file=sys.stderr)
        print(f"  Save CSV: {args.save_csv}", file=sys.stderr)
        print(f"  Save NPY: {args.save_npy}", file=sys.stderr)
        print(file=sys.stderr)
    
    # Parsing corpus
    print(f"Parsing corpus...", file=sys.stderr)
    state = build_from_corpus(config)
    
    # Estrae counts e stats
    counts = state.counts
    stats = state.stats

    # Calcola probabilità
    print(f"\nCalcolo probabilità e smoothing...", file=sys.stderr)
    models = build_probability_arrays(
        counts=counts,
        alphabet=args.alphabet,
        alpha=args.alpha,
        verbose=args.verbose,
        need_arrays=args.save_npy
    )

    # Salva output
    print(f"\nSalvataggio output...", file=sys.stderr)

    generated_files = []
    metadata_models = {}

    for model_type in ['inword', 'continuous']:
        for n in range(args.min_n, args.max_n + 1):
            model = models[model_type][n]
            base_name = f"paisa_{n}grams_{model_type}"

            # CSV
            if args.save_csv:
                csv_file = csv_dir / f"{base_name}.csv"
                write_csv(
                    csv_data=model['csv_data'],
                    output_file=str(csv_file),
                    n=n,
                    model_type=model_type,
                    min_count=args.min_count,
                    verbose=args.verbose
                )
                generated_files.append(str(csv_file.relative_to(output_dir)))

            # NPY
            if args.save_npy:
                logprob_file = npy_dir / f"{base_name}_logprob.npy"
                counts_file = npy_dir / f"{base_name}_counts.npy"
                write_npy(
                    logprob_array=model['logprob_array'],
                    counts_array=model['counts_array'],
                    logprob_file=str(logprob_file),
                    counts_file=str(counts_file),
                    verbose=args.verbose
                )
                generated_files.append(str(logprob_file.relative_to(output_dir)))
                generated_files.append(str(counts_file.relative_to(output_dir)))

            # Metadata modello
            model_key = f"{n}_{model_type}"
            metadata_models[model_key] = {
                'total_ngrams': model['total_ngrams'],
                'unique_ngrams': model['unique_ngrams'],
                'vocab_size': model['vocab_size'],
                'default_log_probability': model['default_log_probability'],
                'csv_file': f"csv/{base_name}.csv" if args.save_csv else None,
                'logprob_npy_file': f"npy/{base_name}_logprob.npy" if args.save_npy else None,
                'counts_npy_file': f"npy/{base_name}_counts.npy" if args.save_npy else None
            }

    # Frequenze lettere
    letter_counts = state.letter_counts
    alpha_letters = config.alpha_letters
    total_letters = sum(letter_counts.values())
    
    if args.verbose:
        print(f"\nFrequenze lettere:", file=sys.stderr)
        print(f"  Totale lettere: {total_letters:,}", file=sys.stderr)
    
    # CSV lettere
    if args.save_csv:
        letter_csv_file = csv_dir / "paisa_letter_frequencies.csv"
        write_letter_csv(
            letter_counts=letter_counts,
            alpha_letters=alpha_letters,
            output_file=str(letter_csv_file),
            alphabet=args.alphabet,
            verbose=args.verbose
        )
        generated_files.append(str(letter_csv_file.relative_to(output_dir)))
    
    # NPY lettere
    if args.save_npy:
        letter_counts_file = npy_dir / "paisa_letter_counts.npy"
        letter_freq_file = npy_dir / "paisa_letter_frequencies.npy"
        letter_logprob_file = npy_dir / "paisa_letter_logprob.npy"
        write_letter_npy(
            letter_counts=letter_counts,
            alpha_letters=alpha_letters,
            counts_file=str(letter_counts_file),
            frequencies_file=str(letter_freq_file),
            logprob_file=str(letter_logprob_file),
            alphabet=args.alphabet,
            verbose=args.verbose
        )
        generated_files.append(str(letter_counts_file.relative_to(output_dir)))
        generated_files.append(str(letter_freq_file.relative_to(output_dir)))
        generated_files.append(str(letter_logprob_file.relative_to(output_dir)))
    
    # Calcola top lettere per metadata
    top_letters = []
    if total_letters > 0:
        letter_data = []
        for letter_id in range(len(args.alphabet)):
            letter = args.alphabet[letter_id]
            count = letter_counts.get(letter_id, 0)
            frequency = count / total_letters
            letter_data.append({
                'letter': letter,
                'letter_id': letter_id,
                'count': count,
                'frequency': frequency
            })
        letter_data.sort(key=lambda x: -x['count'])
        top_letters = [
            {
                'letter': item['letter'],
                'letter_id': item['letter_id'],
                'count': item['count'],
                'frequency': round(item['frequency'], 6),
                'rank': i + 1
            }
            for i, item in enumerate(letter_data[:10])
        ]

    # Metadata generale
    metadata = {
        'corpus': 'PAISA',
        'corpus_file': args.corpus_file,
        'output_dir': args.output_dir,
        'alphabet': args.alphabet,
        'base': len(args.alphabet),
        'invalid_word_policy': args.invalid_word_policy,
        'min_n': args.min_n,
        'max_n': args.max_n,
        'alpha': args.alpha,
        'min_count': args.min_count,
        'continuous_boundary_mode': args.continuous_boundary_mode,
        'generation_date': datetime.now().isoformat(),
        'execution_mode': 'parallel' if args.workers > 1 else 'sequential',
        'workers': args.workers,
        'batch_size': args.batch_size if args.workers > 1 else None,
        'max_pending_batches': args.max_pending_batches if args.workers > 1 else None,
        'normalization': {
            'unicode_form': 'NFKD',
            'strip_accents': True,
            'uppercase': True,
            'only_AZ': True,
            'ignore_comment_lines_starting_with': '#',
            'remove_xml_tags': True,
            'reset_on_text_block_end': True
        },
        'stats': stats,
        'models': metadata_models,
        'letters': {
            'total_letters': total_letters,
            'unique_letters': len([lid for lid in range(len(args.alphabet)) if letter_counts.get(lid, 0) > 0]),
            'alpha_letters': alpha_letters,
            'csv_file': 'csv/paisa_letter_frequencies.csv' if args.save_csv else None,
            'counts_npy_file': 'npy/paisa_letter_counts.npy' if args.save_npy else None,
            'frequencies_npy_file': 'npy/paisa_letter_frequencies.npy' if args.save_npy else None,
            'logprob_npy_file': 'npy/paisa_letter_logprob.npy' if args.save_npy else None,
            'top_letters': top_letters
        },
        'generated_files': generated_files
    }

    # Salva metadata
    metadata_file = output_dir / 'metadata.json'
    write_metadata(
        metadata=metadata,
        output_file=str(metadata_file),
        verbose=args.verbose
    )

    # Salva README generato
    readme_file = output_dir / 'README_GENERATED_MODEL.md'
    write_generated_model_readme(
        metadata=metadata,
        output_file=str(readme_file),
        verbose=args.verbose
    )

    print(f"\n{'='*70}", file=sys.stderr)
    print(f"✓ COMPLETATO", file=sys.stderr)
    print(f"{'='*70}", file=sys.stderr)
    print(f"\nFile generati in: {args.output_dir}", file=sys.stderr)
    print(f"  - metadata.json", file=sys.stderr)
    print(f"  - README_GENERATED_MODEL.md", file=sys.stderr)
    if args.save_csv:
        print(f"  - csv/*.csv ({args.max_n - args.min_n + 1} x 2 modelli)", file=sys.stderr)
    if args.save_npy:
        print(f"  - npy/*.npy ({(args.max_n - args.min_n + 1) * 2 * 2} array)", file=sys.stderr)
    print(file=sys.stderr)


if __name__ == '__main__':
    main()

