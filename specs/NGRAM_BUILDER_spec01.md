Agisci come sviluppatore Python senior, esperto di NLP computazionale e crittoanalisi classica.

Devi implementare un modulo Python per costruire modelli statistici di trigrammi e quadrigrammi italiani a partire dal corpus PAISÀ, da usare nello scoring di plaintext candidati durante un attacco al cifrario di Vigenère.

Il corpus PAISÀ è un file testuale grande, circa 1.8 GB, con righe di commento, tag <text ...>...</text>, testo italiano, punteggiatura, accenti, numeri, URL e caratteri sporchi. Lo script deve leggere il file in streaming, senza caricarlo interamente in memoria.

OBIETTIVO

Generare quattro modelli statistici:

1. trigrammi intra-parola
2. quadrigrammi intra-parola
3. trigrammi continuous / extra-parola
4. quadrigrammi continuous / extra-parola

I modelli serviranno a valutare se un plaintext candidato ottenuto da Vigenère assomiglia statisticamente all’italiano.

CONTESTO CRITTOANALITICO

Il plaintext candidato, dopo decifratura Vigenère, sarà normalizzato come sequenza continua:

- solo lettere A-Z;
- maiuscolo;
- senza accenti;
- senza spazi;
- senza punteggiatura.

Il modulo deve quindi produrre modelli compatibili con questo scenario.

Tuttavia, per ridurre rumore e migliorare lo scoring, bisogna distinguere due famiglie di n-grammi:

1. INWORD:
   n-grammi estratti solo dentro singole parole.
   Sono meno numerosi ma più puliti e più forti come evidenza linguistica.

2. CONTINUOUS:
   n-grammi estratti da segmenti testuali normalizzati concatenando parole consecutive.
   Possono attraversare spazi tra parole, ma non devono attraversare delimitatori forti, tag, numeri, simboli o fine documento.

DEFINIZIONI

Modello INWORD:
- estrae n-grammi solo all’interno delle singole parole;
- non attraversa spazi, punteggiatura, apostrofi, numeri, simboli o tag.

Esempio:
GATTO

Trigrammi:
GAT, ATT, TTO

Quadrigrammi:
GATT, ATTO

Modello CONTINUOUS:
- concatena parole consecutive entro segmenti testuali puliti;
- può attraversare spazi tra parole;
- non deve attraversare delimitatori forti;
- non deve attraversare tag, commenti, fine blocco </text>, numeri, simboli o punteggiatura forte.

Esempio:
"Il gatto nero dorme"

Segmento continuous:
ILGATTONERODORME

Esempio:
"Il gatto nero. Dorme sul divano."

Segmenti continuous:
ILGATTONERO
DORMESULDIVANO

Non generare n-grammi che attraversano il punto tra NERO e DORME.

PARSING PAISÀ

Il corpus PAISÀ può avere struttura simile a:

##
# This is the Paisà corpus...
##
<text id="7000001" url="http://www.02blog.it/">
finito agli arresti domiciliari
</text>
<text id="7000002" url="http://www.06blog.it/">
Il nome è tutto un programma, ed è quasi ridicolo chiedere: “Cosa vendete qui?”.
</text>

Lo script deve:

- ignorare righe che iniziano con "#";
- riconoscere apertura blocco <text ...>;
- riconoscere chiusura blocco </text>;
- processare solo contenuto dentro i blocchi <text>;
- rimuovere tag XML/HTML residui con regex <[^>]+>;
- conservare il contenuto testuale, ma non i tag;
- resettare il buffer continuous alla chiusura di ogni </text>;
- non creare n-grammi artificiali tra documenti diversi;
- ignorare contenuto fuori dai blocchi <text>.

NORMALIZZAZIONE

Regole obbligatorie:

- usare Unicode NFKD;
- rimuovere i diacritici;
- convertire lettere accentate nella rispettiva lettera non accentata;
- convertire in maiuscolo;
- mantenere solo lettere A-Z;
- trattare i caratteri non alfabetici come delimitatori;
- non eliminare una parola solo perché contiene accenti: prima rimuovere gli accenti, poi filtrare.

Esempi obbligatori:

perché -> PERCHE
città -> CITTA
può -> PUO
più -> PIU
università -> UNIVERSITA
così -> COSI
E' fondamentale -> E | FONDAMENTALE
quest'inspiegabile -> QUEST | INSPIEGABILE
larghezza 1/8" -> LARGHEZZA
<b>ciao</b> -> CIAO

Lettere accentate:

à á â ä ã å -> A
è é ê ë -> E
ì í î ï -> I
ò ó ô ö õ -> O
ù ú û ü -> U
ç -> C

DELIMITATORI

Per INWORD:
- qualunque carattere non A-Z separa parole.

Per CONTINUOUS:
- spazi semplici possono essere attraversati;
- delimitatori forti interrompono il segmento.

Delimitatori forti:

. , ; : ! ?
( ) [ ] { }
" ' “ ” « »
/ \ |
- – —
numeri
simboli
tag
URL
email
markup residuo
fine blocco </text>

Implementare parametro CLI:

--continuous-boundary-mode {sentence,strict,line,document}

Default:
sentence

Significato:

sentence:
- attraversa spazi tra parole;
- resetta il segmento continuous su punteggiatura forte, numeri e simboli.

strict:
- ogni carattere non alfabetico interrompe il segmento;
- non genera cross-word n-gram.

line:
- resetta il segmento a ogni riga.

document:
- concatena tutto dentro il blocco <text>, esclusi tag e commenti.

CODIFICA BASE 26

Ogni n-gramma deve essere rappresentato anche come intero base 26.

Alfabeto:
ABCDEFGHIJKLMNOPQRSTUVWXYZ

Mappatura:
A=0, B=1, ..., Z=25

Formula:
id = (((c0 * 26) + c1) * 26 + c2) ...

Esempi:

GAT:
G=6, A=0, T=19
id = ((6 * 26) + 0) * 26 + 19 = 4075

GATT:
G=6, A=0, T=19, T=19
id = (((6 * 26) + 0) * 26 + 19) * 26 + 19 = 105969

Implementare:

- ngram_to_id(ngram: str, alphabet: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ") -> int
- id_to_ngram(idx: int, n: int, alphabet: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ") -> str

La codifica non deve produrre collisioni per n fisso.

IMPORTANTE:
- gli ID di trigrammi e quadrigrammi sono significativi solo conoscendo n;
- non mischiare trigrammi e quadrigrammi nello stesso array;
- usare array separati per n=3 e n=4;
- usare uint32 per ngram_id;
- usare uint64 o int64 per counts;
- usare float32 per log_probability negli array NPY.

CONTEGGI

Usare Counter separati con chiave intera ngram_id:

counts["inword"][3]
counts["inword"][4]
counts["continuous"][3]
counts["continuous"][4]

Non usare stringhe come chiave nei contatori principali.

L’estrazione deve avvenire con finestre sovrapposte.

Esempio:
GATTO

n=3:
GAT, ATT, TTO

n=4:
GATT, ATTO

Per ogni modello e n, calcolare:

- total_ngrams;
- unique_ngrams;
- vocab_size = 26^n;
- count per ngram_id.

PROBABILITÀ E SMOOTHING

Calcolare per ogni modello:

probability = count / total_ngrams

Usare smoothing additivo:

smoothed_probability =
    (count + alpha) / (total_ngrams + alpha * vocab_size)

log_probability =
    ln(smoothed_probability)

default_log_probability =
    ln(alpha / (total_ngrams + alpha * vocab_size))

Il parametro alpha deve essere configurabile:

--alpha FLOAT

Default consigliato:
0.01

Interpretazione:

- alpha basso: modello più severo;
- alpha alto: modello più permissivo;
- per PAISÀ e quadrigrammi italiani partire da alpha=0.01.

Gli n-grammi non osservati devono avere probabilità piccola ma non zero. Non usare -inf.

DISTINZIONE TRA SCORE BONUS E LOG-PROBABILITY

Il modulo deve produrre principalmente log_probability smoothed, utile per scoring probabilistico.

Tuttavia, nei CSV devono essere presenti anche count e probability grezza, così da poter usare eventualmente gli n-grammi anche come “bonus di evidenza”:

- se n-gramma osservato: aumenta lo score;
- se n-gramma non osservato: nessun bonus.

Questa logica bonus non deve essere necessariamente implementata nel builder, ma i dati prodotti devono renderla possibile.

OUTPUT

Generare sia CSV sia NPY.

La directory output deve avere questa struttura:

assets/ngrams_paisa/
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

CONTRATTO DI OUTPUT CSV

Ogni CSV rappresenta un modello statistico n-gram distinto.

Esempi:

- paisa_3grams_inword.csv:
  trigrammi estratti solo dentro parole.

- paisa_4grams_inword.csv:
  quadrigrammi estratti solo dentro parole.

- paisa_3grams_continuous.csv:
  trigrammi estratti da segmenti continuous.

- paisa_4grams_continuous.csv:
  quadrigrammi estratti da segmenti continuous.

Ogni CSV deve avere esattamente queste colonne:

1. ngram

Rappresentazione testuale dell’n-gramma.

Esempi:
GAT
GATT
IONE

2. ngram_id

Rappresentazione intera base 26 dell’n-gramma.

L’alfabeto è:
A=0, B=1, ..., Z=25.

Formula:
id = (((c0 * 26) + c1) * 26 + c2) ...

Esempio:
GAT:
G=6, A=0, T=19
id = ((6 * 26) + 0) * 26 + 19 = 4075

GATT:
id = (((6 * 26) + 0) * 26 + 19) * 26 + 19 = 105969

3. n

Lunghezza dell’n-gramma.

Valori attesi:
3 oppure 4.

4. model

Tipo di modello.

Valori ammessi:
inword
continuous

inword:
n-grammi estratti solo dentro singole parole.

continuous:
n-grammi estratti da segmenti testuali normalizzati concatenando parole consecutive, senza attraversare delimitatori forti.

5. count

Numero di occorrenze osservate nel corpus per quell’n-gramma in quello specifico modello.

Esempio:
Se GATT appare 9876 volte nel modello quadrigrammi inword, count=9876.

6. probability

Probabilità grezza osservata nel corpus:

probability = count / total_ngrams_del_modello

Non usa smoothing.
Può essere usata per audit o analisi descrittiva.

7. smoothed_probability

Probabilità con smoothing additivo:

smoothed_probability =
    (count + alpha) / (total_ngrams_del_modello + alpha * vocab_size)

Dove:
alpha = parametro di smoothing
vocab_size = 26^n

Serve per evitare probabilità zero per n-grammi mai osservati.

8. log_probability

Logaritmo naturale della smoothed_probability:

log_probability = ln(smoothed_probability)

Questo è il valore da usare nello scoring statistico dei plaintext candidati.

9. rank

Posizione dell’n-gramma nel modello, ordinando per count decrescente.
rank=1 indica l’n-gramma più frequente del modello.

Esempio CSV:

ngram,ngram_id,n,model,count,probability,smoothed_probability,log_probability,rank
IONE,154321,4,inword,98544,0.0002704,0.0002703,-8.2161,1
GATT,105969,4,inword,9876,0.0000271,0.0000271,-10.5152,342
QZXW,302120,4,inword,1,0.0000000027,0.0000000028,-19.6964,234521

NOTA IMPORTANTE SUI CSV

I CSV devono contenere solo gli n-grammi osservati nel corpus con count >= min_count.
Gli n-grammi non osservati non compaiono nel CSV.
Il loro valore di log_probability è comunque disponibile negli array NPY tramite default_log_probability, riportato nel metadata.json.

CONTRATTO DI OUTPUT NPY

I file NPY sono array NumPy pensati per scoring veloce.

Per ogni modello vengono generati due array:

1. *_logprob.npy

Array NumPy monodimensionale di dtype float32.

Dimensione:
- 26^3 = 17.576 per trigrammi
- 26^4 = 456.976 per quadrigrammi

La posizione i dell’array contiene la log_probability dell’n-gramma con ngram_id = i.

Esempio:

quad_inword = np.load("paisa_4grams_inword_logprob.npy")
quad_inword[105969]

restituisce lo score log_probability del quadrigramma GATT.

Se un n-gramma non è stato osservato nel corpus, la posizione corrispondente contiene default_log_probability.

2. *_counts.npy

Array NumPy monodimensionale di dtype uint64 o int64.

Dimensione:
- 26^3 = 17.576 per trigrammi
- 26^4 = 456.976 per quadrigrammi

La posizione i contiene il count osservato dell’n-gramma con ngram_id = i.

Se un n-gramma non è stato osservato, il valore è 0.

Esempio pratico:

import numpy as np

quad_scores = np.load("npy/paisa_4grams_inword_logprob.npy")
quad_counts = np.load("npy/paisa_4grams_inword_counts.npy")

ngram_id = 105969  # GATT

score = quad_scores[ngram_id]
count = quad_counts[ngram_id]

La relazione tra CSV e NPY deve essere garantita:
per ogni riga del CSV:

npy_logprob[ngram_id] == log_probability
npy_counts[ngram_id] == count

Il test suite deve verificare questa coerenza almeno su alcuni n-grammi noti.

DEFAULT_LOG_PROBABILITY

Per ogni modello, metadata.json deve riportare:

default_log_probability

Questo valore è assegnato negli array *_logprob.npy a tutti gli n-grammi non osservati.

Formula:

default_log_probability =
    ln(alpha / (total_ngrams_del_modello + alpha * vocab_size))

Esempio:

se il quadrigramma QZXW non è stato osservato:

quad_scores[ngram_to_id("QZXW")] == default_log_probability

USO NELLO SCORING VIGENÈRE

Il README_GENERATED_MODEL.md deve includere un esempio di scoring:

import numpy as np

quad_cont = np.load("npy/paisa_4grams_continuous_logprob.npy")

def score_quadgrams(plain_nums, quad_scores):
    total = 0.0
    for i in range(len(plain_nums) - 3):
        a = plain_nums[i]
        b = plain_nums[i + 1]
        c = plain_nums[i + 2]
        d = plain_nums[i + 3]
        idx = (((a * 26) + b) * 26 + c) * 26 + d
        total += float(quad_scores[idx])
    return total / max(1, len(plain_nums) - 3)

Il README deve spiegare che:
- plain_nums è il plaintext candidato rappresentato come interi 0..25;
- idx è l’ngram_id base 26;
- quad_scores[idx] recupera lo score logaritmico del quadrigramma;
- lo score medio permette di confrontare plaintext candidati.

METADATA

Generare metadata.json con almeno:

{
  "corpus": "PAISA",
  "corpus_file": "...",
  "output_dir": "...",
  "alphabet": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
  "base": 26,
  "min_n": 3,
  "max_n": 4,
  "alpha": 0.01,
  "continuous_boundary_mode": "sentence",
  "normalization": {
    "unicode_form": "NFKD",
    "strip_accents": true,
    "uppercase": true,
    "only_AZ": true,
    "ignore_comment_lines_starting_with": "#",
    "remove_xml_tags": true,
    "reset_on_text_block_end": true
  },
  "stats": {
    "total_lines_read": ...,
    "total_text_blocks": ...,
    "total_words": ...,
    "total_chars_inword": ...,
    "total_chars_continuous": ...
  },
  "models": {
    "3_inword": {
      "total_ngrams": ...,
      "unique_ngrams": ...,
      "vocab_size": 17576,
      "default_log_probability": ...,
      "csv_file": "csv/paisa_3grams_inword.csv",
      "logprob_npy_file": "npy/paisa_3grams_inword_logprob.npy",
      "counts_npy_file": "npy/paisa_3grams_inword_counts.npy"
    },
    "4_inword": {
      "total_ngrams": ...,
      "unique_ngrams": ...,
      "vocab_size": 456976,
      "default_log_probability": ...,
      "csv_file": "csv/paisa_4grams_inword.csv",
      "logprob_npy_file": "npy/paisa_4grams_inword_logprob.npy",
      "counts_npy_file": "npy/paisa_4grams_inword_counts.npy"
    },
    "3_continuous": {
      "total_ngrams": ...,
      "unique_ngrams": ...,
      "vocab_size": 17576,
      "default_log_probability": ...,
      "csv_file": "csv/paisa_3grams_continuous.csv",
      "logprob_npy_file": "npy/paisa_3grams_continuous_logprob.npy",
      "counts_npy_file": "npy/paisa_3grams_continuous_counts.npy"
    },
    "4_continuous": {
      "total_ngrams": ...,
      "unique_ngrams": ...,
      "vocab_size": 456976,
      "default_log_probability": ...,
      "csv_file": "csv/paisa_4grams_continuous.csv",
      "logprob_npy_file": "npy/paisa_4grams_continuous_logprob.npy",
      "counts_npy_file": "npy/paisa_4grams_continuous_counts.npy"
    }
  },
  "generated_files": [...]
}

README_GENERATED_MODEL.md

Lo script deve generare automaticamente un file Markdown chiamato:

README_GENERATED_MODEL.md

Il file deve contenere almeno queste sezioni:

# Modello n-grammi PAISÀ generato

## 1. Scopo
Spiegare che il modello è stato generato per scoring crittoanalitico di plaintext candidati Vigenère.

## 2. Corpus sorgente
- nome corpus;
- percorso file;
- numero righe lette;
- numero blocchi <text> processati;
- numero parole;
- data generazione.

## 3. Normalizzazione applicata
Elencare:
- Unicode NFKD;
- accenti rimossi e lettere conservate;
- maiuscolo;
- solo A-Z;
- tag rimossi;
- righe commento ignorate;
- comportamento continuous_boundary_mode.

## 4. Modelli generati
Spiegare:
- 3grams inword;
- 4grams inword;
- 3grams continuous;
- 4grams continuous.

Per ogni modello riportare:
- total_ngrams;
- unique_ngrams;
- vocab_size;
- default_log_probability;
- file CSV;
- file NPY logprob;
- file NPY counts.

## 5. Formato CSV
Spiegare dettagliatamente ogni colonna:
- ngram;
- ngram_id;
- n;
- model;
- count;
- probability;
- smoothed_probability;
- log_probability;
- rank.

## 6. Formato NPY
Spiegare:
- array monodimensionali;
- indice = ngram_id;
- dimensione 26^n;
- *_logprob.npy;
- *_counts.npy;
- dtype usati;
- valore per n-grammi non osservati.

## 7. Codifica base 26
Spiegare formula ed esempi:
- GAT = 4075;
- GATT = 105969.

## 8. Smoothing e alpha
Spiegare:
- cos’è alpha;
- formula smoothed_probability;
- formula default_log_probability;
- alpha usato nella generazione.

## 9. Esempio di caricamento Python
Mostrare codice per caricare NPY e interrogare uno score.

## 10. Esempio di scoring Vigenère
Mostrare codice minimo per calcolare lo score di un plaintext candidato in formato intero.

## 11. Avvertenze
Spiegare:
- i CSV non contengono n-grammi non osservati;
- gli NPY contengono invece tutti gli ID possibili;
- i modelli sono coerenti solo con testi normalizzati A-Z;
- continuous e inword misurano aspetti diversi;
- non confrontare score prodotti con alpha o corpus diversi senza cautela.

CLI

Creare script:

build_paisa_ngrams.py

Parametri:

--corpus-file PATH
Percorso al file PAISÀ.

--output-dir PATH
Directory output.

--min-n INT
Default 3.

--max-n INT
Default 4.

--alphabet STRING
Default ABCDEFGHIJKLMNOPQRSTUVWXYZ.

--alpha FLOAT
Default 0.01.

--min-count INT
Default 1. Applicato solo ai CSV, non agli NPY.

--encoding STRING
Default utf-8.

--progress-every INT
Default 100000.

--continuous-boundary-mode {sentence,strict,line,document}
Default sentence.

--save-csv
Salva CSV.

--save-npy
Salva NPY.

--self-test
Esegue test interni rapidi e termina.

--verbose
Output dettagliato.

Esempio:

python3 build_paisa_ngrams.py \
  --corpus-file ./corpus/paisa.raw.txt \
  --output-dir ./assets/ngrams_paisa \
  --min-n 3 \
  --max-n 4 \
  --alpha 0.01 \
  --continuous-boundary-mode sentence \
  --save-csv \
  --save-npy \
  --progress-every 100000

ARCHITETTURA CODICE

Puoi implementare in un singolo file, ma con funzioni modulari.

Funzioni richieste:

- strip_accents(text: str) -> str
- remove_tags(text: str) -> str
- normalize_to_words(text: str) -> list[str]
- split_line_into_segments(text: str, mode: str) -> list[list[str]]
- ngram_to_id(ngram: str, alphabet: str) -> int
- id_to_ngram(idx: int, n: int, alphabet: str) -> str
- iter_ngrams_from_word(word: str, n: int)
- iter_ngrams_from_text(text: str, n: int)
- update_inword_counts(words, counts, min_n, max_n)
- update_continuous_counts(segments, counts, min_n, max_n)
- parse_paisa_stream(...)
- build_probability_arrays(...)
- write_csv(...)
- write_npy(...)
- write_metadata(...)
- write_generated_model_readme(...)

PERFORMANCE

Il file è grande:
- leggere riga per riga;
- non caricare tutto in memoria;
- non memorizzare tutte le parole;
- usare Counter su ID interi;
- convertire ID in stringa solo quando si scrive CSV;
- stampare progress periodicamente.

Non usare pandas nel core.
Non usare dizionari con stringhe nel ciclo caldo.
Non usare regex inutilmente pesanti nel ciclo caldo.
Usare numpy solo per la generazione degli array NPY.

TEST

Usare pytest.

Generare directory:

tests/
├── test_normalization.py
├── test_encoding.py
├── test_extraction.py
├── test_paisa_parser.py
├── test_outputs.py
├── test_generated_readme.py
└── fixtures/
    └── small_paisa_sample.txt

Fixture small_paisa_sample.txt:

##
# commento da ignorare
##
<text id="1" url="http://example.com">
Il gatto nero. Dorme sul divano.
</text>
<text id="2" url="http://example.com/2">
Perché la città è più bella?
quest'inspiegabile cosa
</text>
<text id="3" url="http://example.com/3">
larghezza 1/8": quella da corsa
</text>

Test normalizzazione:
- "perché" -> ["PERCHE"]
- "città" -> ["CITTA"]
- "può più così" -> ["PUO", "PIU", "COSI"]
- "E' fondamentale" -> ["E", "FONDAMENTALE"]
- "quest'inspiegabile" -> ["QUEST", "INSPIEGABILE"]
- "larghezza 1/8\"" -> ["LARGHEZZA"]
- "<b>ciao</b>" -> ["CIAO"]

Test codifica base 26:
- ngram_to_id("A") == 0
- ngram_to_id("B") == 1
- ngram_to_id("Z") == 25
- ngram_to_id("AA") == 0
- ngram_to_id("AB") == 1
- ngram_to_id("AZ") == 25
- ngram_to_id("BA") == 26
- ngram_to_id("GAT") == 4075
- ngram_to_id("GATT") == 105969
- id_to_ngram(ngram_to_id("GATT"), 4) == "GATT"
- id_to_ngram(ngram_to_id("IONE"), 4) == "IONE"
- id_to_ngram(ngram_to_id("AAA"), 3) == "AAA"
- id_to_ngram(ngram_to_id("ZZZ"), 3) == "ZZZ"

Test collisioni:
- generare tutti i 26^3 trigrammi;
- verificare che gli ID siano unici;
- per quadrigrammi, testare almeno casi limite e campione ampio, oppure test completo se il tempo è accettabile.

Test estrazione inword:
Input:
GATTO NERO

Inword trigrammi attesi:
GAT, ATT, TTO, NER, ERO

Inword quadrigrammi attesi:
GATT, ATTO, NERO

Non devono comparire cross-word come TON o ONE nel modello inword.

Test continuous sentence:
Input:
Il gatto nero dorme

Continuous:
ILGATTONERODORME

Devono poter comparire cross-word come TTON o TONE.

Input:
Il gatto nero. Dorme sul divano.

In modalità sentence:
non devono comparire n-grammi che attraversano il punto tra NERO e DORME.
Quindi non devono comparire EROD o RODO se derivano dall’attraversamento della frase.

Test parsing PAISÀ:
- righe # ignorate;
- tag <text> e </text> ignorati;
- contenuto dentro <text> processato;
- contenuto fuori da <text> ignorato;
- buffer continuous resettato su </text>.

Test output:
Eseguire builder su fixture in directory temporanea.
Verificare:
- metadata.json esiste;
- README_GENERATED_MODEL.md esiste;
- CSV esistono se --save-csv;
- NPY esistono se --save-npy;
- dimensione array trigrammi = 26^3;
- dimensione array quadrigrammi = 26^4;
- per n-gramma noto il count array è > 0;
- per n-gramma non osservato logprob == default_log_probability;
- CSV contiene colonne richieste.

Test coerenza CSV/NPY:
Per alcune righe note del CSV:
- npy_counts[ngram_id] == count;
- npy_logprob[ngram_id] è uguale a log_probability entro tolleranza numerica.

Test smoothing:
- n-grammi osservati hanno log_probability maggiore del default;
- n-grammi non osservati non hanno -inf;
- alpha è applicato correttamente.

Test documentazione generata:
Verificare che README_GENERATED_MODEL.md:
- contenga le sezioni principali;
- citi alpha;
- citi alphabet e base;
- spieghi CSV;
- spieghi NPY;
- contenga np.load;
- contenga almeno un esempio di scoring;
- citi i file generati;
- sia coerente con metadata.json sui nomi dei file principali.

SELF TEST

Implementare --self-test che:
- crea un mini-corpus temporaneo;
- esegue parsing, normalizzazione, conteggi e output;
- verifica alcune asserzioni base;
- stampa OK o FAILED;
- ritorna exit code 0 se tutto passa.

README DEL PROGETTO

Generare anche README.md con:
- scopo del modulo;
- formato PAISÀ;
- regole di normalizzazione;
- differenza inword/continuous;
- spiegazione ngram_id base 26;
- spiegazione CSV vs NPY;
- spiegazione alpha e smoothing;
- comandi di esempio;
- come eseguire i test;
- raccomandazione: provare prima su fixture o estratto piccolo, poi sul corpus da 1.8 GB.

DEPENDENCIES

requirements.txt:

numpy
pytest

Non usare pandas nel core.

QUALITÀ

- Python 3.11+
- type hints
- docstring
- gestione errori robusta
- messaggi chiari
- funzioni modulari e testabili
- nessuna dipendenza obbligatoria eccetto numpy per --save-npy
- pytest solo per test
- non usare pandas nel core
- non caricare il corpus in memoria

OUTPUT FINALE RICHIESTO

Genera:

1. build_paisa_ngrams.py oppure modulo strutturato sotto src/ngram_builder;
2. requirements.txt;
3. tests/ con i test descritti;
4. README.md;
5. fixture small_paisa_sample.txt;
6. supporto a generazione:
   - CSV;
   - NPY;
   - metadata.json;
   - README_GENERATED_MODEL.md.

IMPORTANTE

Questo modulo è per crittoanalisi Vigenère.
I CSV sono per audit umano.
Gli NPY sono per scoring veloce.
Gli n-grammi devono essere coerenti con plaintext normalizzato A-Z.
Non creare n-grammi artificiali da commenti, tag, numeri, simboli o attraversamenti tra documenti.