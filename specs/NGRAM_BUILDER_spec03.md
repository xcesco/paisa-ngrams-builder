SPECIFICA AGGIUNTIVA: GENERAZIONE FREQUENZE DELLE LETTERE ITALIANE

Il modulo build_paisa_ngrams.py deve generare, oltre ai modelli di trigrammi e quadrigrammi, anche un modello statistico delle frequenze delle singole lettere A-Z derivate dallo stesso corpus PAISÀ normalizzato.

OBIETTIVO

Le frequenze delle lettere serviranno nello script di attacco Vigenère per:

1. valutare la plausibilità delle singole colonne del ciphertext dopo split per lunghezza chiave;
2. stimare i migliori shift Caesar per ogni colonna;
3. calcolare chi-square distance tra frequenze osservate e frequenze italiane attese;
4. calcolare uno score monogramma/log-likelihood sul plaintext candidato completo;
5. affiancare gli score a trigrammi/quadrigrammi nel ranking finale delle chiavi candidate.

CONTESTO CRITTOANALITICO

Nel Vigenère, una volta ipotizzata una lunghezza chiave L, il ciphertext viene diviso in L colonne. Ogni colonna è cifrata con un singolo shift di Cesare.

Per ogni colonna, provando i 26 shift, si può confrontare la distribuzione delle lettere decifrate con la distribuzione attesa dell’italiano.

Questa componente non sostituisce trigrammi e quadrigrammi, ma serve come filtro robusto e stabile per ridurre lo spazio delle chiavi candidate.

NORMALIZZAZIONE

Le frequenze delle lettere devono essere calcolate usando la stessa normalizzazione già definita per gli n-grammi:

- Unicode NFKD;
- rimozione diacritici;
- lettere accentate convertite nella corrispondente lettera non accentata;
- maiuscolo;
- solo A-Z;
- commenti # ignorati;
- tag XML/HTML rimossi;
- contenuto fuori dai blocchi <text> ignorato.

Esempi:

perché -> PERCHE
città -> CITTA
può -> PUO
più -> PIU
è -> E

Le lettere devono essere contate dopo la normalizzazione, non prima.

SORGENTE DEI CONTEGGI

Le frequenze delle lettere devono essere calcolate su tutto il testo utile del corpus PAISÀ processato, indipendentemente dal modello inword/continuous.

In pratica:

- per ogni blocco <text>;
- normalizzare il contenuto;
- estrarre le parole normalizzate;
- contare tutte le lettere A-Z presenti nelle parole;
- ignorare tutto ciò che non è A-Z.

Esempio:

"Il gatto nero."

Normalizzato:
IL GATTO NERO

Conteggi:
I=1
L=1
G=1
A=1
T=2
O=2
N=1
E=1
R=1

STRUTTURE DATI

Durante il parsing mantenere:

letter_counts: array/lista/dizionario di 26 interi

Mappatura:

A=0
B=1
...
Z=25

Tipi consigliati:

- counts: uint64 o int64;
- frequency/log_probability: float64 in fase di calcolo;
- array NPY finali:
  - counts: uint64 o int64;
  - logprob: float32;
  - frequency: float32, se generata.

CALCOLO PROBABILITÀ LETTERE

Per ogni lettera i:

count_i = numero occorrenze della lettera i
total_letters = somma di tutti i count_i

frequency_i = count_i / total_letters

Applicare smoothing additivo anche alle lettere:

smoothed_frequency_i =
    (count_i + alpha_letters) / (total_letters + alpha_letters * 26)

log_probability_i =
    ln(smoothed_frequency_i)

Parametro CLI da aggiungere:

--alpha-letters FLOAT

Default:
usare lo stesso valore di --alpha, se non specificato.

Oppure:
default 0.01.

Nel metadata indicare chiaramente il valore effettivo usato.

OUTPUT DA GENERARE

Aggiungere questi file nella directory output:

assets/ngrams_paisa/
├── metadata.json
├── README_GENERATED_MODEL.md
├── csv/
│   └── paisa_letter_frequencies.csv
└── npy/
    ├── paisa_letter_counts.npy
    ├── paisa_letter_frequencies.npy
    └── paisa_letter_logprob.npy

CSV LETTERE

Generare il file:

csv/paisa_letter_frequencies.csv

Colonne obbligatorie:

1. letter
   Lettera A-Z.

2. letter_id
   Intero 0..25 secondo la codifica:
   A=0, B=1, ..., Z=25.

3. count
   Numero di occorrenze osservate nel corpus normalizzato.

4. frequency
   Frequenza grezza:
   count / total_letters

5. smoothed_frequency
   Frequenza con smoothing:
   (count + alpha_letters) / (total_letters + alpha_letters * 26)

6. log_probability
   Logaritmo naturale della smoothed_frequency.

7. rank
   Posizione della lettera ordinando per count decrescente.
   rank=1 indica la lettera più frequente.

Esempio CSV:

letter,letter_id,count,frequency,smoothed_frequency,log_probability,rank
E,4,12345678,0.1179,0.1179,-2.1382,1
A,0,12003456,0.1146,0.1146,-2.1666,2
I,8,10987654,0.1049,0.1049,-2.2545,3

Ordinamento:
- ordinare per count decrescente;
- in caso di pari count, ordinare per letter_id crescente.

NPY LETTERE

Generare:

1. npy/paisa_letter_counts.npy

Array NumPy monodimensionale di lunghezza 26.
dtype: uint64 o int64.
La posizione i contiene il count della lettera con letter_id=i.

Esempio:
letter_counts[0] -> count di A
letter_counts[4] -> count di E

2. npy/paisa_letter_frequencies.npy

Array NumPy monodimensionale di lunghezza 26.
dtype: float32.
La posizione i contiene frequency_i grezza.

3. npy/paisa_letter_logprob.npy

Array NumPy monodimensionale di lunghezza 26.
dtype: float32.
La posizione i contiene log_probability_i calcolata con smoothing.

Esempio uso:

import numpy as np

letter_logprob = np.load("npy/paisa_letter_logprob.npy")

score = 0.0
for letter_id in plaintext_nums:
    score += float(letter_logprob[letter_id])

score = score / len(plaintext_nums)

METADATA

Aggiornare metadata.json aggiungendo una sezione:

"letters": {
  "total_letters": ...,
  "unique_letters": ...,
  "alpha_letters": 0.01,
  "csv_file": "csv/paisa_letter_frequencies.csv",
  "counts_npy_file": "npy/paisa_letter_counts.npy",
  "frequencies_npy_file": "npy/paisa_letter_frequencies.npy",
  "logprob_npy_file": "npy/paisa_letter_logprob.npy",
  "top_letters": [
    {"letter": "E", "letter_id": 4, "count": ..., "frequency": ..., "rank": 1},
    {"letter": "A", "letter_id": 0, "count": ..., "frequency": ..., "rank": 2}
  ]
}

Aggiornare anche "generated_files" includendo i nuovi file.

README_GENERATED_MODEL.md

Aggiornare il file README_GENERATED_MODEL.md aggiungendo una sezione:

## Frequenze delle lettere

La sezione deve spiegare:

- perché sono state generate;
- come sono state calcolate;
- che usano la stessa normalizzazione degli n-grammi;
- significato di letter_id;
- significato di count, frequency, smoothed_frequency, log_probability;
- file CSV generato;
- file NPY generati;
- come caricare i file in Python;
- come usarli nello scoring Vigenère.

Includere esempio:

import numpy as np

letter_logprob = np.load("npy/paisa_letter_logprob.npy")

def score_letters(plain_nums):
    total = 0.0
    for x in plain_nums:
        total += float(letter_logprob[x])
    return total / max(1, len(plain_nums))

Includere esempio di chi-square per una colonna:

def chi_square_column(column_nums, expected_freq):
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

Spiegare che:
- per la selezione degli shift Vigenère, valori chi-square più bassi sono migliori;
- per log-likelihood monogramma, valori medi meno negativi sono migliori;
- questa metrica deve affiancare trigrammi/quadrigrammi, non sostituirli.

CLI

Aggiungere parametro:

--alpha-letters FLOAT

Descrizione:
Parametro di smoothing per le frequenze delle lettere.
Se non specificato, usare lo stesso valore di --alpha.

Esempio comando:

python3 build_paisa_ngrams.py \
  --corpus-file ./corpus/paisa.raw.txt \
  --output-dir ./assets/ngrams_paisa \
  --min-n 3 \
  --max-n 4 \
  --alpha 0.01 \
  --alpha-letters 0.01 \
  --continuous-boundary-mode sentence \
  --save-csv \
  --save-npy \
  --workers 8 \
  --batch-size 1000

PARALLELIZZAZIONE

La generazione delle frequenze delle lettere deve funzionare sia in modalità sequenziale sia in modalità parallela.

In modalità parallela:

- ogni worker deve produrre letter_counts locali;
- BatchResult deve includere anche letter_counts;
- merge_batch_result deve sommare i letter_counts locali nei letter_counts globali;
- il risultato finale deve essere identico tra workers=1 e workers>1.

Aggiornare BatchResult:

BatchResult:
- counts n-grammi;
- letter_counts;
- stats locali.

Aggiornare BuilderState:

BuilderState:
- counts n-grammi;
- letter_counts globali;
- stats globali.

TEST AGGIUNTIVI

Tutti i test precedenti devono continuare a passare.

Aggiungere i seguenti test.

1. test_letter_counts_basic

Input:
"ABBA"

Atteso:
A=2
B=2
tutte le altre lettere=0
total_letters=4

2. test_letter_counts_with_accents

Input:
"perché città più può"

Normalizzato:
PERCHE CITTA PIU PUO

Verificare che:
- E includa la è/é normalizzata;
- A includa à normalizzata;
- U includa ù normalizzata;
- O includa ò normalizzata;
- nessuna lettera accentata venga eliminata.

3. test_letter_counts_ignore_non_letters

Input:
"A1/B- C!"

Atteso:
A=1
B=1
C=1
nessun conteggio per numeri o simboli.

4. test_letter_output_files_exist

Eseguire builder su fixture.

Verificare esistenza di:
- csv/paisa_letter_frequencies.csv
- npy/paisa_letter_counts.npy
- npy/paisa_letter_frequencies.npy
- npy/paisa_letter_logprob.npy

5. test_letter_npy_shapes

Verificare:
- letter_counts.shape == (26,)
- letter_frequencies.shape == (26,)
- letter_logprob.shape == (26,)

6. test_letter_csv_columns

Verificare che paisa_letter_frequencies.csv abbia colonne:

letter,letter_id,count,frequency,smoothed_frequency,log_probability,rank

7. test_letter_csv_npy_consistency

Per alcune righe del CSV:
- letter_counts[letter_id] == count;
- letter_frequencies[letter_id] == frequency entro tolleranza;
- letter_logprob[letter_id] == log_probability entro tolleranza.

8. test_letter_probabilities_sum_to_one

Verificare:
- somma delle frequency grezze circa 1.0;
- somma delle smoothed_frequency circa 1.0.

9. test_letter_logprob_not_inf

Verificare:
- nessun valore in letter_logprob.npy è inf o -inf;
- nessun NaN.

10. test_parallel_equals_sequential_letter_counts

Eseguire builder sulla fixture con:
- workers=1
- workers=2

Verificare:
- letter_counts identici;
- letter_frequencies identiche entro tolleranza;
- letter_logprob identici entro tolleranza.

11. test_metadata_contains_letters

Verificare che metadata.json contenga:
- sezione "letters";
- total_letters;
- alpha_letters;
- csv_file;
- counts_npy_file;
- frequencies_npy_file;
- logprob_npy_file;
- top_letters.

12. test_generated_readme_mentions_letter_frequencies

Verificare che README_GENERATED_MODEL.md:
- contenga una sezione sulle frequenze delle lettere;
- spieghi l’uso per Vigenère;
- contenga esempio np.load per paisa_letter_logprob.npy;
- contenga o menzioni chi-square;
- spieghi che le frequenze lettere affiancano gli n-grammi.

CRITERI DI ACCETTAZIONE

La modifica è accettata solo se:

1. vengono generati CSV e NPY delle frequenze lettere;
2. i conteggi lettere sono coerenti con la normalizzazione;
3. i file NPY sono indicizzati da letter_id 0..25;
4. metadata.json documenta i nuovi file;
5. README_GENERATED_MODEL.md spiega la struttura e l’uso;
6. modalità sequenziale e parallela producono gli stessi letter_counts;
7. tutti i test precedenti e nuovi passano.