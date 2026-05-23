# Architettura degli Array NumPy

**Documentazione tecnica sul formato NPY per modelli n-grammi PAISÀ**

---

## 📋 Indice

- [Motivazione della Scelta](#motivazione-della-scelta)
- [Architettura degli Array](#architettura-degli-array)
- [Creazione degli Array](#creazione-degli-array)
- [Organizzazione dei File](#organizzazione-dei-file)
- [Utilizzo Pratico](#utilizzo-pratico)
- [Performance](#performance)
- [Alfabeti Personalizzati](#alfabeti-personalizzati)
- [Esempi Avanzati](#esempi-avanzati)

---

## 🎯 Motivazione della Scelta

### Perché NumPy?

Il progetto utilizza **NumPy** per la generazione e gestione degli array di scoring per diverse ragioni tecniche e prestazionali:

#### 1. **Lookup O(1) Garantito**

Durante un attacco Vigenère, è necessario valutare **migliaia o milioni** di plaintext candidati. Ogni plaintext viene scorato attraverso l'estrazione di n-grammi e il recupero delle rispettive probabilità logaritmiche.

**Con NumPy**:
```python
quad_id = (((a * 26) + b) * 26 + c) * 26 + d  # O(1)
score = quad_scores[quad_id]                    # O(1)
```

**Senza NumPy** (dizionario Python):
```python
ngram = f"{chr(a+65)}{chr(b+65)}{chr(c+65)}{chr(d+65)}"  # costruzione stringa
score = scores_dict.get(ngram, default)                   # hash lookup O(1) ma più lento
```

L'accesso diretto tramite array eliminando:
- Costruzione di stringhe
- Hash computation
- Collisioni di hash
- Overhead di dict internals

#### 2. **Memoria Compatta e Contigua**

Gli array NumPy sono **contigui in memoria**:
- Cache-friendly (CPU cache line optimization)
- Dimensione fissa nota a priori: `base^n × sizeof(dtype)`
- Nessun overhead di strutture dati complesse

**Confronto dimensioni** (alfabeto 26, quadrigrammi):

| Formato | Dimensione | Note |
|---------|------------|------|
| **NPY logprob** | **~1.8 MB** | array `float32[456976]` |
| **NPY counts** | **~3.5 MB** | array `uint64[456976]` |
| CSV (gzipped) | ~5-15 MB | solo n-grammi osservati |
| Dict Python (pickle) | ~10-30 MB | overhead chiavi stringa |

#### 3. **Compatibilità con Ecosistema Scientifico**

NumPy è lo standard de facto per:
- Machine Learning (PyTorch, TensorFlow)
- Data Science (pandas, scikit-learn)
- Numerical computing
- Interoperabilità C/Fortran

#### 4. **Garanzia di Default Values**

Gli array NPY permettono di inizializzare **tutti i 26^n o 25^n elementi** con un valore di default:

```python
logprob_array = np.full(vocab_size, default_log_prob, dtype=np.float32)
```

Questo significa che **anche n-grammi mai osservati** nel corpus hanno uno score valido, evitando:
- Errori di chiave mancante
- Necessità di controlli `if ngram_id in dict`
- Probabilità zero (che diventerebbero `-inf` in log-space)

#### 5. **Velocità di I/O**

Il formato `.npy` è ottimizzato per:
- **Caricamento rapido**: struttura binaria con header minimale
- **Memoria mappata**: possibilità di `mmap` per file molto grandi
- **Nessun parsing**: dati letti direttamente come array

**Benchmark caricamento**:
```
CSV (456K righe):        ~2-5 secondi
NPY logprob (456K elem): ~0.01 secondi  (200-500× più veloce)
```

---

## 🏗️ Architettura degli Array

### Struttura Generale

Il sistema genera **8 array NPY** per modello completo (alfabeto 26):

```
npy/
├── paisa_3grams_inword_logprob.npy      # 17.576 × float32
├── paisa_3grams_inword_counts.npy       # 17.576 × uint64
├── paisa_4grams_inword_logprob.npy      # 456.976 × float32
├── paisa_4grams_inword_counts.npy       # 456.976 × uint64
├── paisa_3grams_continuous_logprob.npy  # 17.576 × float32
├── paisa_3grams_continuous_counts.npy   # 17.576 × uint64
├── paisa_4grams_continuous_logprob.npy  # 456.976 × float32
├── paisa_4grams_continuous_counts.npy   # 456.976 × uint64
├── paisa_letter_counts.npy              # 26 × int64
├── paisa_letter_frequencies.npy         # 26 × float32
└── paisa_letter_logprob.npy             # 26 × float32
```

### Dimensionamento degli Array

Le dimensioni sono **funzione della base dell'alfabeto**:

| Alfabeto | Base | Trigrammi | Quadrigrammi | Lettere |
|----------|------|-----------|--------------|---------|
| Standard (A-Z) | 26 | 26³ = 17.576 | 26⁴ = 456.976 | 26 |
| Playfair (senza J) | 25 | 25³ = 15.625 | 25⁴ = 390.625 | 25 |

**Formula generale**:
```
vocab_size = base^n
```

### Tipi di Dati (dtype)

| Array | dtype | Range | Motivazione |
|-------|-------|-------|-------------|
| `*_logprob.npy` | `float32` | ±3.4×10³⁸ | Sufficiente per log probability [-50, 0] |
| `*_counts.npy` | `uint64` | 0 a 2⁶⁴-1 | Supporta corpus enormi (>18 exabytes) |
| `letter_counts.npy` | `int64` | ±2⁶³-1 | Compatibilità con statistiche |
| `letter_frequencies.npy` | `float32` | [0, 1] | Probabilità normalizzate |
| `letter_logprob.npy` | `float32` | (-∞, 0] | Log probability |

**Perché `float32` invece di `float64`?**
- Precisione sufficiente: 7 cifre decimali significative
- **Memoria dimezzata**: 1.8 MB vs 3.6 MB per quadrigrammi
- Velocità: operazioni SIMD più efficienti su float32

---

## 🔧 Creazione degli Array

### Pipeline di Generazione

#### 1. **Fase di Conteggio**

Durante il parsing del corpus:

```python
# Counter separati per modello e n
counts = {
    'inword': {
        3: Counter(),  # Counter[ngram_id] -> count
        4: Counter()
    },
    'continuous': {
        3: Counter(),
        4: Counter()
    }
}

letter_counts = Counter()  # Counter[letter_id] -> count
```

**Chiave tecnica**: i Counter usano `ngram_id` interi, **non stringhe**, per efficienza.

#### 2. **Calcolo Probabilità con Smoothing**

Dopo il parsing completo, per ogni modello (inword/continuous) e lunghezza n:

```python
vocab_size = base ** n
total_ngrams = sum(counter.values())

# Smoothing additivo (Laplace)
alpha = 0.01  # configurabile via CLI

# Default per n-grammi non osservati
default_log_prob = math.log(alpha / (total_ngrams + alpha * vocab_size))

# Inizializza array con default
logprob_array = np.full(vocab_size, default_log_prob, dtype=np.float32)
counts_array = np.zeros(vocab_size, dtype=np.uint64)
```

#### 3. **Popolazione Array**

Solo per n-grammi **effettivamente osservati**:

```python
for ngram_id, count in counter.items():
    # Probabilità smoothed
    smoothed_prob = (count + alpha) / (total_ngrams + alpha * vocab_size)
    
    # Log probability
    log_prob = math.log(smoothed_prob)
    
    # Popola array
    logprob_array[ngram_id] = log_prob
    counts_array[ngram_id] = count
```

**Risultato**:
- N-grammi osservati: hanno log probability positivamente informativa
- N-grammi non osservati: mantengono `default_log_probability`

#### 4. **Salvataggio NPY**

```python
np.save(logprob_file, logprob_array)
np.save(counts_file, counts_array)
```

Il formato `.npy` include:
- Header con metadata (shape, dtype, endianness)
- Array data in formato binario contiguo

### Creazione Array Lettere

Pipeline analoga per le frequenze delle singole lettere:

```python
# Conteggio durante parsing
for word in normalized_words:
    for char in word:
        if char in alphabet:
            letter_id = alphabet.index(char)
            letter_counts[letter_id] += 1

# Post-processing
total_letters = sum(letter_counts.values())
letter_counts_array = np.zeros(26, dtype=np.int64)
letter_frequencies_array = np.zeros(26, dtype=np.float32)
letter_logprob_array = np.zeros(26, dtype=np.float32)

for letter_id in range(len(alphabet)):
    count = letter_counts.get(letter_id, 0)
    letter_counts_array[letter_id] = count
    
    # Smoothing
    smoothed_freq = (count + alpha_letters) / (total_letters + alpha_letters * len(alphabet))
    letter_frequencies_array[letter_id] = count / total_letters
    letter_logprob_array[letter_id] = math.log(smoothed_freq)
```

---

## 📂 Organizzazione dei File

### Metadata JSON

Ogni generazione produce `metadata.json` che documenta:

```json
{
  "alphabet": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
  "base": 26,
  "alpha": 0.01,
  "models": {
    "4_continuous": {
      "total_ngrams": 1234567890,
      "unique_ngrams": 345678,
      "vocab_size": 456976,
      "default_log_probability": -15.234567,
      "logprob_npy_file": "npy/paisa_4grams_continuous_logprob.npy",
      "counts_npy_file": "npy/paisa_4grams_continuous_counts.npy"
    }
  },
  "letters": {
    "total_letters": 98765432,
    "alpha_letters": 0.01,
    "counts_npy_file": "npy/paisa_letter_counts.npy",
    "frequencies_npy_file": "npy/paisa_letter_frequencies.npy",
    "logprob_npy_file": "npy/paisa_letter_logprob.npy"
  }
}
```

### Relazione CSV-NPY

I **CSV contengono solo n-grammi osservati** (tipicamente 100K-500K righe), mentre **NPY contengono tutti gli ID possibili** (456K elementi).

**CSV**:
```csv
ngram,ngram_id,n,model,count,probability,smoothed_probability,log_probability,rank
IONE,154321,4,continuous,98544,0.0002704,0.0002703,-8.2161,1
GATT,105969,4,continuous,9876,0.0000271,0.0000271,-10.5152,342
```

**NPY**:
```python
quad_logprob[154321]  # -8.2161 (osservato)
quad_logprob[105969]  # -10.5152 (osservato)
quad_logprob[999999]  # -15.234567 (non osservato, default)
```

**Coerenza garantita**:
```python
# Per ogni riga CSV:
assert npy_logprob[ngram_id] ≈ log_probability  (entro ε float32)
assert npy_counts[ngram_id] == count
```

---

## 💼 Utilizzo Pratico

### Caricamento Base

```python
import numpy as np

# Carica array log probability
quad_cont = np.load("npy/paisa_4grams_continuous_logprob.npy")
quad_inword = np.load("npy/paisa_4grams_inword_logprob.npy")
tri_cont = np.load("npy/paisa_3grams_continuous_logprob.npy")

# Carica frequenze lettere
letter_logprob = np.load("npy/paisa_letter_logprob.npy")
letter_freq = np.load("npy/paisa_letter_frequencies.npy")

# Carica metadata per default_log_probability
import json
with open("metadata.json") as f:
    meta = json.load(f)

default_quad = meta["models"]["4_continuous"]["default_log_probability"]
```

### Scoring di un Plaintext Candidato

```python
def score_quadgrams(plaintext_nums: list[int], quad_scores: np.ndarray, base: int = 26) -> float:
    """
    Calcola score logaritmico medio di un plaintext usando quadrigrammi.
    
    Args:
        plaintext_nums: plaintext come lista di interi 0..base-1
        quad_scores: array log probability quadrigrammi
        base: dimensione alfabeto (26 o 25)
        
    Returns:
        Score medio (più alto = più verosimile)
    """
    if len(plaintext_nums) < 4:
        return float('-inf')
    
    total = 0.0
    count = 0
    
    for i in range(len(plaintext_nums) - 3):
        a, b, c, d = plaintext_nums[i:i+4]
        
        # Calcola ngram_id base N
        ngram_id = (((a * base) + b) * base + c) * base + d
        
        # Accumula score
        total += float(quad_scores[ngram_id])
        count += 1
    
    return total / count
```

### Scoring Combinato

```python
def score_plaintext_combined(
    plain_nums: list[int], 
    quad_scores: np.ndarray,
    tri_scores: np.ndarray,
    letter_scores: np.ndarray,
    weights: dict = None,
    base: int = 26
) -> float:
    """
    Score combinato usando quadrigrammi, trigrammi e lettere.
    """
    if weights is None:
        weights = {'quad': 0.5, 'tri': 0.3, 'letter': 0.2}
    
    # Score quadrigrammi
    quad_score = 0.0
    for i in range(len(plain_nums) - 3):
        a, b, c, d = plain_nums[i:i+4]
        idx = (((a * base) + b) * base + c) * base + d
        quad_score += float(quad_scores[idx])
    quad_score /= max(1, len(plain_nums) - 3)
    
    # Score trigrammi
    tri_score = 0.0
    for i in range(len(plain_nums) - 2):
        a, b, c = plain_nums[i:i+3]
        idx = ((a * base) + b) * base + c
        tri_score += float(tri_scores[idx])
    tri_score /= max(1, len(plain_nums) - 2)
    
    # Score lettere (monogrammi)
    letter_score = sum(float(letter_scores[x]) for x in plain_nums) / len(plain_nums)
    
    # Combinazione pesata
    return (weights['quad'] * quad_score + 
            weights['tri'] * tri_score + 
            weights['letter'] * letter_score)
```

### Chi-Square per Colonne Vigenère

```python
def chi_square_column(column_nums: list[int], expected_freq: np.ndarray) -> float:
    """
    Calcola chi-square distance tra distribuzione osservata e attesa.
    
    Usato per stimare lo shift Caesar migliore per ogni colonna Vigenère.
    
    Args:
        column_nums: colonna del ciphertext (interi 0..25)
        expected_freq: array frequenze attese (es. da paisa_letter_frequencies.npy)
        
    Returns:
        Chi-square statistic (più basso = migliore match)
    """
    observed = np.zeros(26, dtype=np.int64)
    for x in column_nums:
        observed[x] += 1
    
    n = len(column_nums)
    chi2 = 0.0
    
    for i in range(26):
        expected = expected_freq[i] * n
        if expected > 0:
            chi2 += ((observed[i] - expected) ** 2) / expected
    
    return chi2
```

---

## ⚡ Performance

### Benchmark Operazioni

Test su Intel i7 (single-thread), alfabeto 26, quadrigrammi:

| Operazione | Tempo | Note |
|------------|-------|------|
| Caricamento NPY | ~10 ms | 456K elementi |
| Scoring 1 plaintext (1000 char) | ~50 μs | 997 quadrigrammi |
| Scoring 10K plaintext | ~0.5 s | batch processing |
| Chi-square 1 colonna (100 char) | ~5 μs | 26 bin histogram |

### Memory Footprint

| Modello | RAM Occupata |
|---------|--------------|
| 1 array quadrigrammi logprob | ~1.8 MB |
| 1 array trigrammi logprob | ~70 KB |
| 1 array lettere | ~100 bytes |
| **Totale 8 array + 3 lettere** | **~12 MB** |

**Vantaggio**: Tutti i modelli caricabili contemporaneamente anche su sistemi embedded.

### Ottimizzazioni Implementate

1. **Vectorizzazione limitata**: il loop su quadrigrammi è sequenziale per semplicità, ma NumPy operations sono comunque ottimizzate internamente

2. **Evitamento allocazioni**: riuso buffer, nessuna costruzione stringhe

3. **Memory mapping** (opzionale):
```python
quad_scores = np.load("paisa_4grams_continuous_logprob.npy", mmap_mode='r')
# Array non caricato in RAM, accesso via mmap
```

4. **Cache-friendly access**: accesso sequenziale agli array durante scoring

---

## 🔤 Alfabeti Personalizzati

### Alfabeto Playfair (25 caratteri, senza J)

Il cifrario Playfair usa una griglia 5×5 che richiede esattamente **25 lettere**.

**Comando generazione**:
```bash
uv run build_paisa_ngrams.py \
  --corpus-file ./assets/paisa/paisa.raw.utf8 \
  --output-dir ./assets/ngrams_paisa_alphabet25 \
  --alphabet "ABCDEFGHIKLMNOPQRSTUVWXYZ" \
  --invalid-word-policy drop-word \
  --workers 16 \
  --save-npy
```

**Dimensioni array risultanti**:

| Array | Dimensione alfabeto 25 | vs alfabeto 26 |
|-------|------------------------|----------------|
| Trigrammi | 25³ = **15.625** | -11% |
| Quadrigrammi | 25⁴ = **390.625** | -14.5% |
| Lettere | **25** | -3.8% |

**Mappatura caratteri**:
```python
alphabet_25 = "ABCDEFGHIKLMNOPQRSTUVWXYZ"

# K ha indice 9 (non 10!)
assert alphabet_25[9] == 'K'
assert alphabet_25.index('K') == 9

# Esempio codifica quadrigramma KATT
# K=9, A=0, T=18, T=18
ngram_id = (((9 * 25) + 0) * 25 + 18) * 25 + 18
# = 141093

# Con alfabeto 26 sarebbe stato:
# K=10, quindi id diverso!
```

### Invalid Word Policy: `drop-word`

Con alfabeto a 25 caratteri, parole contenenti **J vengono scartate interamente**:

```python
# Corpus input:
"IL JAZZ NERO JOLLY KILO"

# Con alfabeto 25 e policy drop-word:
# ✓ Parole valide:   IL, NERO, KILO
# ✗ Parole scartate: JAZZ, JOLLY

# Segmenti continuous creati:
#   - IL
#   - NERO
#   - KILO
# (JAZZ e JOLLY interrompono i segmenti)
```

**Importante**: J **non viene convertita in I**, perché:
1. Altererebbe artificialmente le frequenze della lettera I
2. Introdurrebbe bias statistico
3. Il corpus PAISÀ contiene anglicismi, nomi propri, ecc. con J

**Verifica nel metadata**:
```json
{
  "alphabet": "ABCDEFGHIKLMNOPQRSTUVWXYZ",
  "base": 25,
  "invalid_word_policy": "drop-word",
  "models": {
    "4_continuous": {
      "vocab_size": 390625  // 25^4
    }
  },
  "letters": {
    "unique_letters": 25  // max 25, nessuna J
  }
}
```

---

## 🧪 Esempi Avanzati

### Recupero Metadata da Array

```python
import numpy as np
import json

# Carica array e metadata
quad_scores = np.load("npy/paisa_4grams_continuous_logprob.npy")
with open("metadata.json") as f:
    meta = json.load(f)

# Estrai informazioni
base = meta["base"]
alphabet = meta["alphabet"]
default_log_prob = meta["models"]["4_continuous"]["default_log_probability"]
vocab_size = meta["models"]["4_continuous"]["vocab_size"]

# Verifica coerenza
assert quad_scores.shape[0] == vocab_size
assert vocab_size == base ** 4
```

### Analisi n-grammi più/meno frequenti

```python
# Carica counts
quad_counts = np.load("npy/paisa_4grams_continuous_counts.npy")

# Top 10 quadrigrammi più frequenti
top_indices = np.argsort(quad_counts)[-10:][::-1]

for idx in top_indices:
    count = quad_counts[idx]
    # Decodifica ngram_id -> stringa
    ngram = id_to_ngram(idx, n=4, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    print(f"{ngram}: {count:,}")
```

Output esempio:
```
IONE: 98,544
MENT: 87,321
AZIO: 76,543
...
```

### Confronto inword vs continuous

```python
# Carica i due modelli
quad_inword = np.load("npy/paisa_4grams_inword_logprob.npy")
quad_cont = np.load("npy/paisa_4grams_continuous_logprob.npy")

# Plaintext candidato
plaintext = "ILGATTONEROMANGIAILTOPO"
plain_nums = [ord(c) - ord('A') for c in plaintext]

# Score con entrambi
score_inword = score_quadgrams(plain_nums, quad_inword)
score_cont = score_quadgrams(plain_nums, quad_cont)

print(f"Score INWORD:      {score_inword:.4f}")
print(f"Score CONTINUOUS:  {score_cont:.4f}")
print(f"Differenza:        {score_cont - score_inword:.4f}")
```

Tipicamente:
- **CONTINUOUS** ha score più alto per testi con molte parole brevi
- **INWORD** penalizza maggiormente n-grammi cross-word infrequenti

### Validazione integrità array

```python
def validate_npy_arrays(output_dir: str, base: int = 26):
    """Valida che tutti gli array NPY abbiano dimensioni corrette."""
    
    import json
    import numpy as np
    from pathlib import Path
    
    npy_dir = Path(output_dir) / "npy"
    meta_path = Path(output_dir) / "metadata.json"
    
    with open(meta_path) as f:
        meta = json.load(f)
    
    assert meta["base"] == base, f"Base mismatch: {meta['base']} != {base}"
    
    # Verifica trigrammi
    tri_vocab = base ** 3
    for model in ['inword', 'continuous']:
        logprob = np.load(npy_dir / f"paisa_3grams_{model}_logprob.npy")
        counts = np.load(npy_dir / f"paisa_3grams_{model}_counts.npy")
        
        assert logprob.shape == (tri_vocab,), f"Shape error: {logprob.shape}"
        assert counts.shape == (tri_vocab,), f"Shape error: {counts.shape}"
        assert logprob.dtype == np.float32
        assert counts.dtype == np.uint64
    
    # Verifica quadrigrammi
    quad_vocab = base ** 4
    for model in ['inword', 'continuous']:
        logprob = np.load(npy_dir / f"paisa_4grams_{model}_logprob.npy")
        counts = np.load(npy_dir / f"paisa_4grams_{model}_counts.npy")
        
        assert logprob.shape == (quad_vocab,), f"Shape error: {logprob.shape}"
        assert counts.shape == (quad_vocab,), f"Shape error: {counts.shape}"
    
    # Verifica lettere
    letter_counts = np.load(npy_dir / "paisa_letter_counts.npy")
    letter_freq = np.load(npy_dir / "paisa_letter_frequencies.npy")
    letter_logprob = np.load(npy_dir / "paisa_letter_logprob.npy")
    
    assert letter_counts.shape == (base,)
    assert letter_freq.shape == (base,)
    assert letter_logprob.shape == (base,)
    
    # Verifica nessun NaN o Inf
    assert not np.any(np.isnan(logprob))
    assert not np.any(np.isinf(logprob))
    
    print(f"✓ Tutti gli array validati correttamente per base {base}")

# Uso
validate_npy_arrays("./assets/ngrams_paisa_alphabet26", base=26)
validate_npy_arrays("./assets/ngrams_paisa_alphabet25", base=25)
```

---

## 📚 Riferimenti Tecnici

### Formato NPY

Documentazione ufficiale NumPy: https://numpy.org/neps/nep-0001-npy-format.html

**Struttura file `.npy`**:
```
Magic string (6 bytes): \x93NUMPY
Version (2 bytes): 1.0 / 2.0
Header length (2/4 bytes)
Header (dict Python): {'descr': '<f4', 'fortran_order': False, 'shape': (456976,)}
Array data (binario)
```

### Smoothing Additivo

Formula implementata (Laplace smoothing):
```
P(ngram) = (count(ngram) + α) / (N + α × V)

dove:
  N = somma di tutti i count
  V = vocab_size = base^n
  α = parametro smoothing (default 0.01)
```

**Default log probability**:
```
log P(ngram_non_osservato) = ln(α / (N + α × V))
```

Tipicamente: `-15.0` a `-20.0` per quadrigrammi su PAISÀ.

### Codifica Base-N

Formula per n-gramma di lunghezza n:
```
id = (((c₀ × base) + c₁) × base + c₂) × base + ... + c_{n-1}

dove c_i ∈ [0, base-1]
```

**Proprietà**:
- Biunivoca per n fissato
- Range: [0, base^n - 1]
- No collisioni
- Ordinamento lessicografico naturale

---

## ✅ Best Practices

### 1. Sempre caricare metadata.json prima degli array

```python
with open("metadata.json") as f:
    meta = json.load(f)

base = meta["base"]
alphabet = meta["alphabet"]

# Ora carica array con parametri corretti
quad_scores = np.load("npy/paisa_4grams_continuous_logprob.npy")
```

### 2. Verificare dimensioni array

```python
expected_size = base ** n
assert quad_scores.shape[0] == expected_size
```

### 3. Usare dtype corretti

```python
# Evitare conversioni implicite
score = float(quad_scores[idx])  # esplicita a float64 se necessario
```

### 4. Gestire edge cases

```python
# Plaintext troppo corto per quadrigrammi
if len(plaintext_nums) < 4:
    return default_log_probability * 4  # penalità
```

### 5. Non mescolare alfabeti

```python
# ✗ ERRATO: usare modello base-26 con plaintext base-25
# ✓ CORRETTO: verificare coerenza
assert len(alphabet_used_in_plaintext) == base_of_model
```

---

## 🔗 Collegamenti

- **README principale**: `../README.md`
- **Specifiche tecniche**: `../specs/`
- **Test alfabeto 25**: `../tests/test_alphabet_25_noj.py`
- **Esempio uso**: vedere sezione "Esempio Scoring Vigenère" nel README

---

**Autore**: Francesco Benincasa  
**Licenza**: MIT  
**Data**: Maggio 2026

