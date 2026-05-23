# N-gram Builder per Corpus PAISÀ

**Strumento a linea di comando per costruire modelli statistici di trigrammi e quadrigrammi italiani dal corpus PAISÀ**

Informazioni su tale corpus sono disponibili https://clarin.eurac.edu/repository/xmlui/handle/20.500.12124/3.

Il corpus può essere scaricato da https://www.corpusitaliano.it/.

Questo strumento è progettato per la **crittoanalisi del cifrario di Vigenère e Playfair**, generando modelli n-grammi utilizzati per lo scoring di plaintext candidati durante l'attacco crittoanalitico.

---

## 📋 Indice

- [Scopo](#scopo)
- [Corpus PAISÀ](#corpus-paisà)
- [Normalizzazione](#normalizzazione)
- [Modelli N-grammi](#modelli-n-grammi)
- [Codifica Base-N](#codifica-base-n-alfabeti-personalizzati)
- [Output](#output)
- [Installazione](#installazione)
- [Utilizzo](#utilizzo)
- [Test](#test)
- [Performance](#performance)
- [Tempi di Esecuzione](#tempi-di-esecuzione)
- [Documentazione Tecnica](#documentazione-tecnica)

---

## 🎯 Scopo

Durante un attacco di crittoanalisi, è necessario valutare quale chiave candidata produce il plaintext più verosimile. 

I **modelli n-grammi statistici** permettono di assegnare uno score a ciascun plaintext candidato basandosi sulla sua somiglianza con l'italiano autentico.

Questo modulo:
- Analizza il corpus PAISÀ (1.8 GB di testo italiano web)
- Estrae trigrammi e quadrigrammi con due approcci: **inword** e **continuous**
- Calcola probabilità con smoothing additivo
- Genera output in formato CSV (audit umano) e NPY (scoring veloce)

---

## 📚 Corpus PAISÀ

Il corpus PAISÀ è un dataset di testo italiano raccolto dal web.

**Formato file**:
```
##
# Commenti da ignorare
##
<text id="7000001" url="http://example.com">
Testo italiano con punteggiatura, accenti, numeri...
</text>
<text id="7000002" url="http://example.com/2">
Altro blocco di testo.
</text>
```

Il parser:
- Ignora righe che iniziano con `#`
- Processa solo contenuto dentro tag `<text>...</text>`
- Rimuove tag XML/HTML residui
- Resetta buffer continuous a ogni `</text>`

### Download del Corpus

Il file completo del corpus PAISÀ (~1.8 GB compresso) può essere scaricato direttamente:

**Con wget**:
```bash
# Crea directory
mkdir -p assets/paisa

# Download del corpus
wget -O assets/paisa/paisa.raw.utf8.gz \
  "https://clarin.eurac.edu/repository/xmlui/bitstream/handle/20.500.12124/3/paisa.raw.utf8.gz?sequence=1&isAllowed=y"

# Decompressione
gunzip assets/paisa/paisa.raw.utf8.gz
```

**Con curl**:
```bash
# Crea directory
mkdir -p assets/paisa

# Download del corpus 
curl -L -o assets/paisa/paisa.raw.utf8.gz \
  "https://clarin.eurac.edu/repository/xmlui/bitstream/handle/20.500.12124/3/paisa.raw.utf8.gz?sequence=1&isAllowed=y"

# Decompressione
gunzip assets/paisa/paisa.raw.utf8.gz
```

**Nota**: Il file decompresso sarà `assets/paisa/paisa.raw.utf8` (circa 1.8 GB).

> **📖 Per informazioni dettagliate sul formato output e utilizzo dei modelli, vedere la sezione [Documentazione Tecnica](#documentazione-tecnica) e la cartella [docs/](docs/)**

---

## 🔧 Normalizzazione

Il plaintext Vigenère decrittato è una sequenza continua di lettere A-Z maiuscole, senza spazi, accenti o punteggiatura.

I modelli n-grammi devono essere **compatibili** con questo formato.

### Pipeline di normalizzazione:

1. **Unicode NFKD**: decomposizione caratteri composti
2. **Rimozione accenti**: lettere accentate → lettere semplici
3. **Maiuscolo**: conversione in uppercase
4. **Solo A-Z**: mantiene solo lettere alfabetiche
5. **Tag rimossi**: elimina marcatura XML/HTML

### Esempi:

| Input | Output |
|-------|--------|
| `perché` | `PERCHE` |
| `città` | `CITTA` |
| `può più così` | `PUO`, `PIU`, `COSI` |
| `E' fondamentale` | `E`, `FONDAMENTALE` |
| `quest'inspiegabile` | `QUEST`, `INSPIEGABILE` |
| `larghezza 1/8"` | `LARGHEZZA` |
| `<b>ciao</b>` | `CIAO` |

### Mappatura accenti:

- `à á â ä ã å → A`
- `è é ê ë → E`
- `ì í î ï → I`
- `ò ó ô ö õ → O`
- `ù ú û ü → U`
- `ç → C`

---

## 🔬 Modelli N-grammi

Il modulo genera **quattro modelli statistici distinti**:

### 1. INWORD (intra-parola)

N-grammi estratti **solo dentro singole parole**.

**Caratteristiche**:
- Più puliti e affidabili
- Non attraversano spazi
- Evidenza linguistica forte

**Esempio**:
```
Input: "GATTO NERO"

Trigrammi inword:
GAT, ATT, TTO, NER, ERO

Quadrigrammi inword:
GATT, ATTO, NERO
```

### 2. CONTINUOUS (extra-parola)

N-grammi estratti da **segmenti testuali concatenati**.

**Caratteristiche**:
- Possono attraversare spazi tra parole
- Non attraversano delimitatori forti (`.`, `,`, `;`, `:`, `!`, `?`, numeri, simboli)
- Catturano transizioni inter-parola tipiche dell'italiano

**Esempio modalità `sentence`** (default):
```
Input: "Il gatto nero. Dorme sul divano."

Segmenti continuous:
ILGATTONERO
DORMESULDIVANO

(Il punto interrompe il segmento)
```

### Modalità boundary continuous:

| Modalità | Comportamento |
|----------|---------------|
| `sentence` | Attraversa spazi, resetta su punteggiatura forte |
| `strict` | Ogni parola è isolata (come inword) |
| `line` | Concatena tutta la riga |
| `document` | Concatena tutto il blocco `<text>` |

---

## 🔢 Codifica Base-N (Alfabeti Personalizzati)

Ogni n-gramma è rappresentato come **intero univoco** usando codifica posizionale base-N, dove N è la lunghezza dell'alfabeto.

### Alfabeti Supportati

| Alfabeto | Caratteri | Base | Uso |
|----------|-----------|------|-----|
| Standard | `ABCDEFGHIJKLMNOPQRSTUVWXYZ` | 26 | Cifrario di Vigenère |
| Playfair | `ABCDEFGHIKLMNOPQRSTUVWXYZ` (senza J) | 25 | Cifrario Playfair (griglia 5×5) |

### Mappatura Caratteri → Indici

**Alfabeto 26**:
| A | B | C | ... | J | K | ... | Z |
|---|---|---|-----|---|---|-----|---|
| 0 | 1 | 2 | ... | 9 | 10 | ... | 25 |

**Alfabeto 25** (senza J):
| A | B | C | ... | I | K | L | ... | Z |
|---|---|---|-----|---|---|---|-----|---|
| 0 | 1 | 2 | ... | 8 | 9 | 10 | ... | 24 |

### Formula di Codifica

```
id = (((c₀ × base) + c₁) × base + c₂) × base + ...
```

### Esempi di Codifica

**Base 26 (Standard)**:
| N-gramma | Formula | ID |
|----------|---------|-----|
| `AAA` | `((0×26)+0)×26+0` | 0 |
| `GAT` | `((6×26)+0)×26+19` | 4075 |
| `GATT` | `(((6×26)+0)×26+19)×26+19` | 105969 |
| `ZZZ` | `((25×26)+25)×26+25` | 17575 |

**Base 25 (Playfair)**:
| N-gramma | Formula | ID |
|----------|---------|-----|
| `AAA` | `((0×25)+0)×25+0` | 0 |
| `GAT` | `((6×25)+0)×25+18` | 3768 |
| `KAT` | `((9×25)+0)×25+18` | 5643 |
| `GATT` | `(((6×25)+0)×25+18)×25+18` | 94218 |
| `KATT` | `(((9×25)+0)×25+18)×25+18` | 141093 |
| `ZZZ` | `25³-1` | 15624 |

**Nota**: Con base 25, la lettera K ha indice 9 (non 10), quindi gli ID sono diversi dalla base 26.

### Dimensioni Spazio N-grammi

| Alfabeto | Trigrammi (n=3) | Quadrigrammi (n=4) |
|----------|-----------------|-------------------|
| Base 26 | 26³ = 17.576 | 26⁴ = 456.976 |
| Base 25 | 25³ = 15.625 | 25⁴ = 390.625 |

### Invalid Word Policy

**Policy `drop-word` (default)**:
- Parole contenenti caratteri non in alphabet → **scartate interamente**
- Le parole scartate **interrompono** i segmenti continuous
- **Nessuna conversione automatica** (es. J non diventa I)

**Esempio alfabeto Playfair (25 caratteri senza J)**:
```
Input: "IL JAZZ NERO JOLLY GATTO"

Parole valide:   IL, NERO, GATTO
Parole scartate: JAZZ, JOLLY (contengono J)

Segmenti continuous creati:
  - IL
  - NERO
  - GATTO
```

### Proprietà della Codifica

✓ **Biunivoca**: nessuna collisione per n fissato  
✓ **Lookup O(1)**: accesso diretto in array NumPy  
✓ **Compatta**: memoria dipende dalla base

---

## 📦 Output

### Directory structure:

```
ngrams/ngrams_paisa_alphabet25/
├── metadata.json                          # Metadati generazione
├── README_GENERATED_MODEL.md              # Documentazione modello
├── csv/
│   ├── paisa_3grams_inword.csv           # Solo n-grammi osservati
│   ├── paisa_4grams_inword.csv
│   ├── paisa_3grams_continuous.csv
│   ├── paisa_4grams_continuous.csv
│   └── paisa_letter_frequencies.csv       # Frequenze lettere
└── npy/
    ├── paisa_3grams_inword_logprob.npy   # Array completi base^n
    ├── paisa_4grams_inword_logprob.npy
    ├── paisa_3grams_continuous_logprob.npy
    ├── paisa_4grams_continuous_logprob.npy
    ├── paisa_3grams_inword_counts.npy
    ├── paisa_4grams_inword_counts.npy
    ├── paisa_3grams_continuous_counts.npy
    ├── paisa_4grams_continuous_counts.npy
    ├── paisa_letter_counts.npy            # Conteggi lettere
    ├── paisa_letter_frequencies.npy       # Frequenze lettere
    └── paisa_letter_logprob.npy           # Log probability lettere
```

> **📖 Per ulteriori dettagli sul formato NPY, architettura degli array e esempi avanzati, consultare [docs/](docs/)**

### Formato CSV:

Colonne:
1. `ngram`: testo n-gramma (es. "GATT")
2. `ngram_id`: ID intero base 26
3. `n`: lunghezza (3 o 4)
4. `model`: tipo (`inword` o `continuous`)
5. `count`: occorrenze osservate
6. `probability`: probabilità grezza
7. `smoothed_probability`: probabilità con smoothing
8. `log_probability`: ln(smoothed_probability) ← **usare per scoring**
9. `rank`: posizione per frequenza

**Nota**: CSV contiene solo n-grammi osservati con `count >= min_count`.

### Formato NPY:

Array NumPy monodimensionali:

**`*_logprob.npy`** (n-grammi):
- Tipo: `float32`
- Dimensione: `base^n` (es. 26³, 25³, 26⁴, 25⁴)
- Indice: `ngram_id`
- Valore: `log_probability`
- N-grammi non osservati: `default_log_probability`

**`*_counts.npy`** (n-grammi):
- Tipo: `uint64`
- Dimensione: `base^n`
- Indice: `ngram_id`
- Valore: count osservato
- N-grammi non osservati: `0`

**`paisa_letter_*.npy`** (frequenze lettere):
- Tipo: `int64` (counts), `float32` (frequencies, logprob)
- Dimensione: `base` (es. 26 o 25)
- Indice: `letter_id` (0 a base-1)
- Valori:
  - `letter_counts.npy`: conteggi osservati
  - `letter_frequencies.npy`: frequenze grezze
  - `letter_logprob.npy`: log probability smoothed

---

## 🛠️ Installazione

```bash
# Clone repository
git clone https://github.com/xcesco/paisa-ngrams-builder
cd paisa-ngrams-builder
```

**Requisiti**:
- Python 3.10+
- `uv` (package manager): https://github.com/astral-sh/uv
- `numpy`: per array NPY
- `pytest`: per test

Il progetto utilizza **uv** per la gestione delle dipendenze. Le dipendenze vengono automaticamente gestite quando si esegue il programma con `uv run`.

---

## 🚀 Utilizzo

### Self-test (verifica installazione):

```bash
uv run python3 build_paisa_ngrams.py --self-test
```

### Esempio completo:

```bash
uv run build_paisa_ngrams.py \
  --corpus-file ./assets/paisa/paisa.raw.utf8 \
  --output-dir ./ngrams/ngrams_paisa_alphabet26 \
  --workers 16 \
  --min-n 3 \
  --max-n 4 \
  --alpha 0.01 \
  --continuous-boundary-mode sentence \
  --save-csv \
  --save-npy \
  --progress-every 100000 \
  --verbose
```

### Test su campione piccolo:

```bash
uv run build_paisa_ngrams.py \
  --corpus-file ./assets/paisa/paisa_sample_short.txt \
  --output-dir ./test_output \
  --save-csv \
  --save-npy \
  --verbose
```

Il risultato di questa esecuzione è disponibile all'indirizzo https://github.com/xcesco/paisa-ngrams-builder/releases/download/assets/ngrams_paisa_alphabet26.zip.

### Esempio con alfabeto a 25 caratteri (senza J):
Questo esempio è molto utile per fare crittoanalisi su crittogrammi sospetti Playfair:
```bash
uv run build_paisa_ngrams.py \
  --corpus-file ./assets/paisa/paisa.raw.utf8 \
  --output-dir ./ngrams/ngrams_paisa_alphabet25 \
  --alphabet "ABCDEFGHIKLMNOPQRSTUVWXYZ" \
  --invalid-word-policy drop-word \
  --workers 16 \
  --min-n 3 \
  --max-n 4 \
  --alpha 0.01 \
  --save-csv \
  --save-npy \
  --verbose
```
Il risultato di questa esecuzione è disponibile all'indirizzo https://github.com/xcesco/paisa-ngrams-builder/releases/download/assets/ngrams_paisa_alphabet25.zip.

**Nota**: Con alfabeto a 25 caratteri, tutte le parole contenenti J (come "jazz", "jeans", "jolly") verranno scartate dal modello.

### Parametri CLI:

| Parametro | Default                      | Descrizione |
|-----------|------------------------------|-------------|
| `--corpus-file` | -                            | Percorso corpus PAISÀ (richiesto) |
| `--output-dir` | `./ngrams/ngrams_paisa`      | Directory output |
| `--min-n` | `3`                          | Lunghezza minima n-gramma |
| `--max-n` | `4`                          | Lunghezza massima n-gramma |
| `--alphabet` | `ABCDEFGHIJKLMNOPQRSTUVWXYZ` | Alfabeto riferimento (personalizzabile) |
| `--invalid-word-policy` | `drop-word`                  | Policy per parole con caratteri non in alphabet |
| `--alpha` | `0.01`                       | Parametro smoothing |
| `--alpha-letters` | `None`                       | Parametro smoothing per lettere (se None usa --alpha) |
| `--min-count` | `1`                          | Count minimo per CSV |
| `--encoding` | `utf-8`                      | Encoding file |
| `--progress-every` | `100000`                     | Frequenza progress |
| `--continuous-boundary-mode` | `sentence`                   | Modalità boundary |
| `--workers` | `1`                          | Numero worker per parallelizzazione |
| `--batch-size` | `1000`                       | Dimensione batch per workers |
| `--save-csv` | -                            | Salva CSV |
| `--save-npy` | -                            | Salva NPY |
| `--verbose` | -                            | Output dettagliato |
| `--self-test` | -                            | Esegue test e termina |

---

## 🧪 Test

### Esegui suite completa:

```bash
uv run pytest tests/ -v
```

### Test coverage:

```bash
uv run pytest tests/ -v --cov=build_paisa_ngrams --cov-report=html
```

### Test specifici:

```bash
pytest tests/test_normalization.py -v
pytest tests/test_encoding.py -v
pytest tests/test_extraction.py -v
pytest tests/test_paisa_parser.py -v
pytest tests/test_outputs.py -v
```

### Test inclusi:

- **Normalizzazione**: accenti, tag, casi edge
- **Codifica base-N**: biunivocità, collisioni, alfabeti personalizzati
- **Alfabeto 25 caratteri**: 23 test specifici per alfabeto senza J
- **Estrazione n-grammi**: inword vs continuous
- **Parsing PAISÀ**: tag, commenti, blocchi
- **Output**: CSV, NPY, metadata, coerenza
- **Smoothing**: probabilità, default values
- **Parallelizzazione**: confronto sequential vs parallel
- **Frequenze lettere**: conteggi, probabilità, smoothing

---

## ⚡ Performance

### Ottimizzazioni implementate:

- **Streaming**: lettura riga per riga senza caricamento completo in memoria
- **ID interi**: Counter su `ngram_id` invece di stringhe
- **Conversione lazy**: stringhe generate solo in fase di output CSV
- **Regex ottimizzate**: pattern compilati per ciclo caldo
- **Parallelizzazione**: supporto multi-worker per corpus grandi

### Requisiti di sistema:

- **RAM**: ~500 MB - 2 GB durante l'esecuzione
- **Spazio disco output** (alfabeto 26):
  - Trigrammi: ~70 KB (logprob) + ~3.5 MB (counts)
  - Quadrigrammi: ~1.8 MB (logprob) + ~3.5 MB (counts)
  - Lettere: ~300 bytes totale
- **Spazio disco output** (alfabeto 25):
  - Trigrammi: ~61 KB (logprob) + ~122 KB (counts)
  - Quadrigrammi: ~1.5 MB (logprob) + ~3.0 MB (counts)
  - Lettere: ~300 bytes totale
- **Output CSV**: dipende da unique n-grammi e `min_count`

---

## ⏱️ Tempi di Esecuzione

### Corpus PAISÀ completo (1.8 GB)
Su macchina dotata di I9 - 32 GB RAM:

| Configurazione | Parsing + Estrazione |
|----------------|---------------------|
| 16 workers | 13m8,031s | 


---

## 📊 Smoothing e Alpha

Per evitare probabilità zero per n-grammi non osservati, viene applicato **smoothing additivo** (Laplace).

**Formule**:
```
smoothed_probability = (count + alpha) / (total_ngrams + alpha × vocab_size)
default_log_probability = ln(alpha / (total_ngrams + alpha × vocab_size))
```

**Parametro alpha**:

| Valore | Effetto | Uso |
|--------|---------|-----|
| 0.001 | Severo, penalizza fortemente n-grammi rari | Testi molto formali |
| **0.01** | **Bilanciato (default raccomandato)** | **Uso generale** |
| 0.1 | Permissivo, minor penalità | Testi con molti neologismi |

---

## 🔍 Esempio Scoring Vigenère

```python
import numpy as np

# Carica modello quadrigrammi continuous
quad_scores = np.load("assets/ngrams_paisa/npy/paisa_4grams_continuous_logprob.npy")

def score_plaintext(plaintext: str, quad_scores) -> float:
    """
    Calcola score logaritmico medio di un plaintext.
    
    Args:
        plaintext: Testo normalizzato A-Z
        quad_scores: Array log probability
        
    Returns:
        Score medio (più alto = più verosimile)
    """
    # Converti in numeri 0..25
    nums = [ord(c) - ord('A') for c in plaintext]
    
    total = 0.0
    count = 0
    
    # Estrai quadrigrammi e somma score
    for i in range(len(nums) - 3):
        a, b, c, d = nums[i], nums[i+1], nums[i+2], nums[i+3]
        ngram_id = (((a * 26) + b) * 26 + c) * 26 + d
        total += quad_scores[ngram_id]
        count += 1
    
    return total / max(1, count)

# Test
plaintext1 = "ILGATTONEROMANGIAILTOPO"
plaintext2 = "QZXWVUTSRQPONMLKJIHGFEDCBA"

score1 = score_plaintext(plaintext1, quad_scores)
score2 = score_plaintext(plaintext2, quad_scores)

print(f"Score testo italiano: {score1:.3f}")
print(f"Score testo random: {score2:.3f}")
# Il testo italiano avrà score significativamente più alto
```

---

## 📝 Avvertenze

**Formato output**:
- **CSV**: solo n-grammi osservati, compatti, editabili, per audit umano
- **NPY**: tutti i base^n ID, binari, veloci per scoring automatico

**Compatibilità modelli**:
- Applicare la stessa normalizzazione ai plaintext candidati
- Verificare `alphabet` e `base` in `metadata.json`
- Modelli con alfabeti diversi non sono intercambiabili

**Uso degli score**:
- INWORD e CONTINUOUS misurano aspetti linguistici diversi e possono essere combinati
- Gli score sono validi solo per confronto relativo tra candidati dello stesso dataset
- Non confrontare score con alpha, corpus o alfabeti diversi

---

## 📚 Documentazione Tecnica

La directory **[`docs/`](docs/)** contiene documentazione tecnica approfondita sul progetto.

### Architettura Array NumPy

Per una comprensione approfondita della struttura degli array NumPy generati, consultare:

**[📄 docs/NUMPY_ARRAYS.md](docs/NUMPY_ARRAYS.md)**

Questo documento spiega:
- **Motivazione della scelta** di NumPy per il formato output
- **Architettura degli array**: struttura, dimensioni, dtype
- **Creazione degli array**: pipeline di generazione, smoothing, popolazione
- **Organizzazione dei file**: relazione CSV-NPY, metadata
- **Utilizzo pratico**: esempi di caricamento e scoring
- **Performance**: benchmark, memory footprint, ottimizzazioni
- **Alfabeti personalizzati**: gestione base-25 per Playfair
- **Esempi avanzati**: validazione, analisi, confronti

---

## 📄 Licenza

Questo progetto è rilasciato sotto **licenza MIT**.

```
MIT License

Copyright (c) 2026 Francesco Benincasa

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Nota sul Corpus PAISÀ**: Il corpus PAISÀ ha una propria licenza separata. Consultare http://www.corpusitaliano.it/ per i termini d'uso.

---

## 🤝 Contributi

Per segnalare bug o suggerire miglioramenti, aprire una issue.

---

## 📚 Riferimenti

- **Corpus PAISÀ**: http://www.corpusitaliano.it/
- **Cifrario Vigenère**: https://it.wikipedia.org/wiki/Cifrario_di_Vigen%C3%A8re
- **Cifrario Playfair**: https://it.wikipedia.org/wiki/Cifrario_Playfair
- 
- **N-gram models**: https://en.wikipedia.org/wiki/N-gram
- **Laplace smoothing**: https://en.wikipedia.org/wiki/Additive_smoothing

---

