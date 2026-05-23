SPECIFICA AGGIUNTIVA: PARALLELIZZAZIONE PER BLOCCHI <text>

Il modulo deve supportare la parallelizzazione del parsing ed estrazione n-grammi usando come unità di lavoro naturale i blocchi PAISÀ:

<text ...>
contenuto testuale
</text>

La parallelizzazione deve essere opzionale e non deve modificare i risultati rispetto alla modalità sequenziale. Tutti i test già previsti devono continuare a passare.

OBIETTIVO

Accelerare la generazione dei modelli n-grammi da PAISÀ senza compromettere la correttezza crittoanalitica.

La strategia corretta è:

1. leggere il file PAISÀ in streaming;
2. identificare blocchi completi <text>...</text>;
3. raggruppare i blocchi in batch;
4. inviare i batch a worker paralleli;
5. ogni worker produce Counter locali e statistiche locali;
6. il processo principale fonde i risultati;
7. solo dopo il merge vengono generati CSV, NPY, metadata.json e README_GENERATED_MODEL.md.

VINCOLI IMPORTANTI

Non caricare mai l’intero corpus in memoria.

Non usare:

corpus.read().split("<text")

perché il file può essere molto grande, circa 1.8 GB.

Non dividere il file per byte o chunk arbitrari, perché si rischia di:
- spezzare tag <text>;
- spezzare caratteri UTF-8;
- spezzare righe;
- generare n-grammi artificiali ai bordi;
- perdere il reset del modello continuous a fine documento.

L’unico split ammesso è lo split logico per blocchi completi <text>...</text>, ottenuto in streaming.

REGOLE DI CORRETTEZZA

Ogni blocco <text>...</text> deve essere trattato come documento indipendente.

Il buffer continuous deve essere sempre resettato alla fine di ogni blocco </text>.

Nessun n-gramma continuous deve attraversare due blocchi <text> diversi.

I tag <text ...> e </text> non devono entrare nel testo processato.

Le righe di commento che iniziano con # devono essere ignorate.

Il contenuto fuori dai blocchi <text> deve essere ignorato.

La modalità parallela deve produrre esattamente gli stessi conteggi della modalità sequenziale.

NUOVI PARAMETRI CLI

Aggiungere:

--workers INT
Numero di processi worker da usare.
Default: 1.

Se --workers 1:
- usare modalità sequenziale;
- nessun multiprocessing.

Se --workers > 1:
- usare multiprocessing con ProcessPoolExecutor;
- parallelizzare per batch di blocchi <text>.

--batch-size INT
Numero di blocchi <text> da inviare a ciascun worker per ogni job.
Default: 1000.

--max-pending-batches INT
Numero massimo di batch pendenti nel ProcessPoolExecutor.
Default: workers * 2.

Se non specificato, calcolarlo automaticamente.

FUNZIONI DA IMPLEMENTARE

Aggiungere o adattare le seguenti funzioni.

1. iter_paisa_text_blocks

Firma consigliata:

iter_paisa_text_blocks(
    corpus_file: Path,
    encoding: str = "utf-8"
) -> Iterator[str]

Responsabilità:
- aprire il file in streaming;
- leggere riga per riga;
- ignorare righe che iniziano con #;
- rilevare apertura <text ...>;
- rilevare chiusura </text>;
- accumulare solo il contenuto interno;
- restituire il contenuto testuale del blocco senza i tag;
- ignorare contenuto fuori dai blocchi;
- gestire errors="replace" o errors="ignore".

Pseudocodice:

inside = False
buffer = []

for line in file:
    stripped = line.strip()

    if stripped.startswith("#"):
        continue

    if stripped.startswith("<text"):
        inside = True
        buffer = []
        continue

    if stripped.startswith("</text>"):
        inside = False
        yield "\n".join(buffer)
        buffer = []
        continue

    if inside:
        buffer.append(line)

Nota:
Se il corpus contiene tag residui dentro il blocco, saranno rimossi dalla normalizzazione successiva con regex <[^>]+>.

2. batched

Firma consigliata:

batched(
    iterator: Iterator[str],
    batch_size: int
) -> Iterator[list[str]]

Responsabilità:
- raggruppare blocchi <text> completi in batch;
- non produrre batch vuoti;
- l’ultimo batch può essere più piccolo di batch_size.

3. process_text_block

Firma consigliata:

process_text_block(
    block_text: str,
    config: BuilderConfig
) -> BlockResult

Responsabilità:
- ricevere il contenuto di un singolo blocco <text>;
- normalizzare;
- estrarre n-grammi inword;
- estrarre n-grammi continuous;
- rispettare continuous_boundary_mode;
- resettare internamente ogni stato continuous del blocco;
- restituire Counter locali e statistiche locali.

4. process_blocks_batch

Firma consigliata:

process_blocks_batch(
    blocks: list[str],
    config: BuilderConfig
) -> BatchResult

Responsabilità:
- processare più blocchi nello stesso worker;
- ridurre overhead di multiprocessing;
- sommare i Counter locali dei blocchi;
- restituire:
  - counts locali;
  - statistiche locali:
    - numero blocchi processati;
    - parole viste;
    - caratteri inword;
    - caratteri continuous;
    - total_ngrams per modello;
    - eventuali righe/blocchi vuoti.

5. merge_batch_result

Firma consigliata:

merge_batch_result(
    global_state: BuilderState,
    batch_result: BatchResult
) -> None

Responsabilità:
- fondere i Counter locali nei Counter globali;
- sommare le statistiche;
- non perdere nessun modello;
- preservare identità dei risultati rispetto alla modalità sequenziale.

6. build_from_corpus

Firma consigliata:

build_from_corpus(
    config: BuilderConfig
) -> BuilderState

Responsabilità:
- orchestrare l’intero processo;
- se workers == 1, usare modalità sequenziale;
- se workers > 1, usare modalità parallela;
- limitare i batch pendenti a max_pending_batches;
- stampare progress periodicamente;
- restituire stato finale unico da cui generare CSV, NPY, metadata e README_GENERATED_MODEL.md.

GESTIONE DEI BATCH PENDENTI

In modalità parallela, non accumulare tutte le future in memoria.

Usare un meccanismo di backpressure:

- mantenere una lista/set di future pendenti;
- se len(pending) >= max_pending_batches:
  - attendere il completamento di almeno una future;
  - fare merge del risultato;
  - liberare memoria;
- continuare a inviare batch.

In alternativa, usare as_completed su finestre di batch.

Il comportamento deve essere robusto anche su corpus molto grandi.

DATACLASS CONSIGLIATE

Aggiungere o adattare:

BuilderConfig:
- corpus_file: Path
- output_dir: Path
- min_n: int
- max_n: int
- alphabet: str
- alpha: float
- min_count: int
- encoding: str
- continuous_boundary_mode: str
- save_csv: bool
- save_npy: bool
- workers: int
- batch_size: int
- max_pending_batches: int | None
- progress_every: int
- verbose: bool

BatchResult:
- counts: dict[str, dict[int, Counter[int]]]
- stats: dict[str, int | float]

BuilderState:
- counts: dict[str, dict[int, Counter[int]]]
- stats: dict[str, int | float]

PICKLING

Poiché ProcessPoolExecutor richiede oggetti serializzabili:
- le funzioni worker devono essere definite a livello modulo, non annidate;
- BuilderConfig deve essere picklable;
- evitare lambda;
- evitare closure non serializzabili.

PROGRESS REPORTING

In modalità sequenziale:
- stampare progress in base a righe lette o blocchi processati.

In modalità parallela:
- stampare progress in base a blocchi <text> letti/inviati e batch completati;
- evitare output rumoroso dai worker;
- solo il processo principale deve stampare progress.

Metadata:
- metadata.json deve riportare:
  - workers;
  - batch_size;
  - max_pending_batches;
  - modalità effettivamente usata: sequential o parallel;
  - total_text_blocks;
  - total_batches_processed.

README_GENERATED_MODEL.md:
- deve includere una sezione che indichi:
  - se il modello è stato generato in modalità sequenziale o parallela;
  - numero worker;
  - batch_size;
  - garanzia che i blocchi <text> sono stati trattati come documenti indipendenti.

TEST AGGIUNTIVI OBBLIGATORI

Tutti i test precedenti devono continuare a passare.

Aggiungere i seguenti test.

1. test_iter_paisa_text_blocks_basic

Usare una fixture con:
- commenti iniziali;
- testo fuori dai blocchi;
- due blocchi <text>;
- righe interne.

Verificare:
- vengono restituiti esattamente due blocchi;
- i tag <text> e </text> non sono presenti nei blocchi restituiti;
- i commenti # non sono presenti;
- contenuto fuori da <text> viene ignorato.

2. test_iter_paisa_text_blocks_ignores_comments

Fixture:

# commento globale
<text id="1">
riga valida
# commento interno da ignorare
altra riga valida
</text>

Verificare:
- il commento interno che inizia con # viene ignorato;
- il blocco contiene solo:
  riga valida
  altra riga valida

3. test_no_cross_block_continuous_ngrams

Fixture:

<text id="1">
ABC
</text>
<text id="2">
DEF
</text>

Con modello continuous e n=4.

Se il buffer non fosse resettato, comparirebbe BCDE o CDEF attraversando blocchi.
Verificare che:
- BCDE non sia presente;
- CDEF non sia presente se attraversa blocco;
- eventuali n-grammi siano generati solo dentro ciascun blocco;
- con blocchi di lunghezza 3 e n=4 non ci siano quadrigrammi continuous.

4. test_batched

Dato un iteratore di 5 blocchi e batch_size=2, verificare:
- batch prodotti: [2, 2, 1];
- nessun batch vuoto.

5. test_process_blocks_batch_equals_sum_of_blocks

Processare tre blocchi:
- singolarmente con process_text_block;
- insieme con process_blocks_batch.

Verificare che:
- i Counter aggregati siano identici;
- le statistiche aggregate siano coerenti.

6. test_parallel_equals_sequential_counts

Usare small_paisa_sample.txt.

Eseguire build_from_corpus con:
- workers=1
- workers=2
- stesso batch_size, ad esempio 1 o 2
- stesso continuous_boundary_mode
- stesso alpha

Verificare:
- counts["inword"][3] identico;
- counts["inword"][4] identico;
- counts["continuous"][3] identico;
- counts["continuous"][4] identico;
- total_text_blocks identico;
- total_words identico;
- total_ngrams per modello identici.

7. test_parallel_equals_sequential_outputs

Generare output in due directory temporanee:
- out_seq con workers=1
- out_par con workers=2

Verificare:
- metadata principali coerenti, tranne campi che indicano modalità/workers;
- array NPY counts identici;
- array NPY logprob uguali entro tolleranza numerica;
- CSV, se ordinati deterministicamente, contengono stessi n-grammi/count/logprob.

Per ordinamento deterministico CSV:
- ordinare prima per count decrescente;
- in caso di pari count, ordinare per ngram_id crescente.

8. test_parallel_metadata_contains_parallel_info

Generare con workers=2.

Verificare che metadata.json contenga:
- "execution_mode": "parallel"
- "workers": 2
- "batch_size": valore usato
- "total_batches_processed" > 0

Generare con workers=1.

Verificare:
- "execution_mode": "sequential"
- "workers": 1

9. test_generated_readme_mentions_parallelization

Generare con workers=2.

Verificare che README_GENERATED_MODEL.md:
- menzioni modalità parallela;
- riporti workers;
- riporti batch_size;
- spieghi che i blocchi <text> sono stati trattati come documenti indipendenti;
- spieghi che nessun n-gramma attraversa due blocchi diversi.

10. test_all_previous_tests_still_pass

Assicurarsi che l’introduzione della parallelizzazione non rompa:
- normalizzazione;
- codifica base 26;
- estrazione inword;
- estrazione continuous;
- output CSV;
- output NPY;
- smoothing;
- README_GENERATED_MODEL.md;
- metadata.json.

CRITERI DI ACCETTAZIONE

La modifica è accettata solo se:

1. la modalità sequenziale funziona come prima;
2. la modalità parallela produce gli stessi risultati della modalità sequenziale;
3. nessun n-gramma attraversa blocchi <text> distinti;
4. i test nuovi e precedenti passano;
5. la memoria resta controllata;
6. non viene caricato l’intero corpus in memoria;
7. metadata e README documentano chiaramente la modalità di esecuzione.

ESEMPIO COMANDO PARALLELO

python3 build_paisa_ngrams.py \
  --corpus-file ./corpus/paisa.raw.txt \
  --output-dir ./assets/ngrams_paisa \
  --min-n 3 \
  --max-n 4 \
  --alpha 0.01 \
  --continuous-boundary-mode sentence \
  --save-csv \
  --save-npy \
  --workers 8 \
  --batch-size 1000 \
  --max-pending-batches 16 \
  --progress-every 100000

NOTA OPERATIVA

Implementare prima e mantenere sempre valida la modalità sequenziale.
La modalità parallela deve essere una ottimizzazione, non una diversa logica di parsing.
Il codice comune di normalizzazione ed estrazione deve essere condiviso tra sequenziale e parallelo.