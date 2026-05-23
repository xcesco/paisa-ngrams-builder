SPECIFICA AGGIUNTIVA REVISIONATA: SUPPORTO E TEST PER ALFABETO A 25 CARATTERI SENZA J

Estendere il modulo build_paisa_ngrams.py e la relativa test suite per verificare che il generatore di n-grammi funzioni correttamente anche con un alfabeto personalizzato a 25 caratteri, cioè l’alfabeto latino senza la lettera J:

ABCDEFGHIKLMNOPQRSTUVWXYZ

Questi test devono garantire che il modulo non abbia valori hardcoded a 26 e che usi sempre:

base = len(alphabet)

anziché:

base = 26

SCELTA METODOLOGICA IMPORTANTE

Con alfabeto a 25 caratteri senza J, la lettera J non deve essere convertita in I.

Motivazione:
- il corpus PAISÀ può contenere parole con J, ad esempio prestiti, nomi propri, anglicismi;
- convertire J in I altererebbe artificialmente le frequenze della lettera I;
- per costruire un modello coerente con un cifrario che non usa J, è preferibile escludere dal modello le parole che contengono caratteri alfabetici non appartenenti all’alfabeto scelto.

Quindi, con alfabeto:

ABCDEFGHIKLMNOPQRSTUVWXYZ

ogni parola che contiene J deve essere scartata interamente dal modello INWORD.

Per il modello CONTINUOUS, una parola contenente J deve interrompere il segmento continuous e non deve contribuire alla concatenazione.

Esempio:

Testo:
IL JAZZ NERO

Con alfabeto a 25 senza J:

- parola IL: valida
- parola JAZZ: non valida, perché contiene J
- parola NERO: valida

INWORD:
- usare IL, se sufficiente per n-grammi;
- scartare JAZZ interamente;
- usare NERO.

CONTINUOUS:
- non produrre ILNERO attraversando JAZZ;
- generare segmenti separati:
  IL
  NERO

Quindi non devono comparire n-grammi cross-word che attraversano una parola scartata.

OBIETTIVO

Verificare che il generatore:

1. accetti un alfabeto personalizzato a 25 caratteri;
2. calcoli correttamente base = 25;
3. converta le lettere in interi secondo l’alfabeto fornito;
4. converta gli interi in lettere secondo l’alfabeto fornito;
5. generi ID n-grammi in base 25;
6. generi array NPY con dimensioni 25^n;
7. generi frequenze lettere con array di dimensione 25;
8. non produca mai ID o array basati implicitamente su 26;
9. scarti interamente le parole contenenti J o altri caratteri alfabetici non appartenenti all’alfabeto scelto;
10. non converta mai J in I;
11. scriva metadata coerente con alphabet e base.

ALFABETO DI TEST

Usare:

alphabet_25 = "ABCDEFGHIKLMNOPQRSTUVWXYZ"

Mappatura attesa:

A = 0
B = 1
C = 2
D = 3
E = 4
F = 5
G = 6
H = 7
I = 8
K = 9
L = 10
M = 11
N = 12
O = 13
P = 14
Q = 15
R = 16
S = 17
T = 18
U = 19
V = 20
W = 21
X = 22
Y = 23
Z = 24

La lettera J non deve essere presente nella mappa.

POLICY PER CARATTERI ALFABETICI NON AMMESSI

Aggiungere o rendere esplicita una policy:

--invalid-word-policy {drop-word}

Per questa versione usare come default:

drop-word

Significato:

- dopo normalizzazione Unicode e rimozione degli accenti, una parola viene considerata valida solo se tutte le sue lettere appartengono all’alfabeto scelto;
- se una parola contiene almeno una lettera alfabetica non presente nell’alfabeto, la parola viene scartata interamente;
- la parola scartata interrompe anche il segmento continuous;
- non generare n-grammi intra-parola dalla parola scartata;
- non generare n-grammi continuous che attraversano la parola scartata.

Esempi con alphabet_25:

JAZZ -> parola scartata
JEANS -> parola scartata
JOLLY -> parola scartata
AJA -> parola scartata
KILO -> parola valida
CITTA -> parola valida
PERCHE -> parola valida

REGOLA PER ACCENTI

Le lettere accentate devono comunque essere convertite nella rispettiva lettera base prima della validazione sull’alfabeto.

Esempi:

perché -> PERCHE -> valida
città -> CITTA -> valida
più -> PIU -> valida
può -> PUO -> valida

La J invece non è un accento e non deve essere convertita in I.

NORMALIZZAZIONE CON ALFABETO PERSONALIZZATO

La normalizzazione deve avvenire in due fasi:

1. Normalizzazione Unicode:
   - usare NFKD;
   - rimuovere diacritici;
   - convertire in maiuscolo.

2. Validazione rispetto all’alfabeto scelto:
   - separare il testo in token/parole alfabetiche;
   - per ogni parola, verificare se tutti i caratteri appartengono all’alfabeto;
   - se sì, conservarla;
   - se no, scartarla interamente.

Importante:
- non usare un filtro carattere-per-carattere che rimuove solo la J da dentro la parola;
- non trasformare JAZZ in AZZ;
- non trasformare AJA in AA;
- non trasformare JEANS in EANS;
- la parola deve essere esclusa interamente.

CONTINUOUS E PAROLE SCARTATE

Per il modello continuous:

- le parole valide consecutive possono essere concatenate;
- una parola scartata interrompe il segmento;
- non si devono creare n-grammi attraversando una parola scartata.

Esempio:

"IL JAZZ NERO"

Parole:
IL -> valida
JAZZ -> scartata
NERO -> valida

Segmenti continuous:
IL
NERO

Non produrre:
ILNERO

Esempio:

"IL GATTO NERO"

Tutte valide.

Segmento continuous:
ILGATTONERO

TEST DA AGGIUNGERE

Creare nuovo file:

tests/test_alphabet_25_noj.py

oppure integrare i test nei file esistenti se più coerente.

1. test_alphabet_25_base

Verificare:

alphabet = "ABCDEFGHIKLMNOPQRSTUVWXYZ"
base = len(alphabet)

assert base == 25
assert "J" not in alphabet
assert alphabet[8] == "I"
assert alphabet[9] == "K"
assert alphabet[24] == "Z"

2. test_char_to_int_alphabet_25

Usare la funzione o logica interna che costruisce char_to_int.

Verificare:

A -> 0
B -> 1
I -> 8
K -> 9
L -> 10
T -> 18
Z -> 24

Verificare inoltre:

"J" not in char_to_int

Se la funzione prevede errore su carattere non presente, verificare che:

char_to_int["J"]

produca KeyError oppure che una funzione safe restituisca None, a seconda dell’implementazione.

3. test_int_to_char_alphabet_25

Verificare:

0 -> A
1 -> B
8 -> I
9 -> K
10 -> L
18 -> T
24 -> Z

Verificare che nessun indice restituisca J:

for i in range(25):
    assert alphabet[i] != "J"

4. test_ngram_to_id_base25_single_letters

Con alphabet_25:

ngram_to_id("A", alphabet_25) == 0
ngram_to_id("B", alphabet_25) == 1
ngram_to_id("I", alphabet_25) == 8
ngram_to_id("K", alphabet_25) == 9
ngram_to_id("Z", alphabet_25) == 24

5. test_ngram_to_id_base25_bigrams

Con alphabet_25:

AA:
id = 0 * 25 + 0 = 0

AB:
id = 0 * 25 + 1 = 1

AZ:
id = 0 * 25 + 24 = 24

BA:
id = 1 * 25 + 0 = 25

IK:
I=8, K=9
id = 8 * 25 + 9 = 209

KA:
K=9, A=0
id = 9 * 25 + 0 = 225

ZZ:
Z=24, Z=24
id = 24 * 25 + 24 = 624

Verificare:

ngram_to_id("AA", alphabet_25) == 0
ngram_to_id("AB", alphabet_25) == 1
ngram_to_id("AZ", alphabet_25) == 24
ngram_to_id("BA", alphabet_25) == 25
ngram_to_id("IK", alphabet_25) == 209
ngram_to_id("KA", alphabet_25) == 225
ngram_to_id("ZZ", alphabet_25) == 624

6. test_ngram_to_id_base25_trigrams

Con alphabet_25:

GAT:
G=6, A=0, T=18

id = ((6 * 25) + 0) * 25 + 18
id = 3768

KAT:
K=9, A=0, T=18

id = ((9 * 25) + 0) * 25 + 18
id = 5643

ZZZ:
id = 25^3 - 1 = 15624

Verificare:

ngram_to_id("GAT", alphabet_25) == 3768
ngram_to_id("KAT", alphabet_25) == 5643
ngram_to_id("ZZZ", alphabet_25) == 15624

7. test_ngram_to_id_base25_quadgrams

Con alphabet_25:

GATT:
G=6, A=0, T=18, T=18

id = (((6 * 25) + 0) * 25 + 18) * 25 + 18
id = 94218

KATT:
K=9, A=0, T=18, T=18

id = (((9 * 25) + 0) * 25 + 18) * 25 + 18
id = 141093

ZZZZ:
id = 25^4 - 1 = 390624

Verificare:

ngram_to_id("GATT", alphabet_25) == 94218
ngram_to_id("KATT", alphabet_25) == 141093
ngram_to_id("ZZZZ", alphabet_25) == 390624

8. test_id_to_ngram_roundtrip_base25

Verificare roundtrip per:

A
Z
IK
KA
GAT
KAT
GATT
KATT
IONE
ZZZZ

Per ciascuno:

idx = ngram_to_id(ngram, alphabet_25)
restored = id_to_ngram(idx, len(ngram), alphabet_25)
assert restored == ngram

9. test_base25_no_collisions_trigrams

Generare tutti i trigrammi possibili sull’alfabeto a 25 caratteri.

Numero atteso:

25^3 = 15625

Per ogni trigramma:
- calcolare ngram_id;
- aggiungerlo a un set.

Verificare:

len(ids) == 15625
min(ids) == 0
max(ids) == 15624

10. test_base25_no_collisions_quadgrams_full

Eseguire test completo sui quadrigrammi.

Numero atteso:

25^4 = 390625

Verificare:

len(ids) == 390625
min(ids) == 0
max(ids) == 390624

Questo test è accettabile perché 390.625 elementi sono gestibili.

11. test_normalization_with_alphabet_25_drops_entire_words_containing_j

Input:

"JAZZ JEANS JOLLY AJA KILO CITTA"

Con alphabet_25 senza J e invalid-word-policy=drop-word.

Parole valide attese:

KILO
CITTA

Parole scartate:

JAZZ
JEANS
JOLLY
AJA

Verificare:
- JAZZ non diventa AZZ;
- JEANS non diventa EANS;
- JOLLY non diventa OLLY;
- AJA non diventa AA;
- nessuna parola contenente J contribuisce al modello;
- KILO viene conservata;
- CITTA viene conservata.

12. test_normalization_with_alphabet_25_accents_preserved_as_base_letters

Input:

"perché città più può così"

Con alphabet_25.

Parole valide attese:

PERCHE
CITTA
PIU
PUO
COSI

Verificare:
- accenti rimossi correttamente;
- nessuna parola viene scartata;
- nessuna lettera valida viene alterata.

13. test_normalization_with_alphabet_25_preserves_letters_after_j

Input:

"KLMNOPQRSTUVWXYZ"

Con alphabet_25.

Verificare che tutte le lettere siano conservate:

KLMNOPQRSTUVWXYZ

e che nessuna venga shiftata o trasformata.

La normalizzazione non deve fare:
K -> J
L -> K
ecc.

Deve solo validare rispetto all’alfabeto.

14. test_inword_counts_base25_excludes_j_words

Input:

"KATTO JAZZ AJA NERO"

Con alphabet_25 e invalid-word-policy=drop-word.

Parole valide:
KATTO
NERO

Parole scartate:
JAZZ
AJA

Trigrammi inword attesi:
KAT
ATT
TTO
NER
ERO

Quadrigrammi inword attesi:
KATT
ATTO
NERO

Verificare che non compaiano:
AZZ
AJA
JA
JAZ
AA
o altri n-grammi derivanti da parole contenenti J.

Verificare ID base 25:

KAT -> 5643
KATT -> 141093

15. test_continuous_counts_base25_excludes_j_words_and_breaks_segment

Input:

"IL JAZZ NERO"

Con alphabet_25.

Parole valide:
IL
NERO

Parola scartata:
JAZZ

Segmenti continuous attesi:
IL
NERO

Verificare che:
- non venga prodotto ILNERO;
- non compaiano n-grammi cross-word tra IL e NERO;
- JAZZ non contribuisca;
- con n=3, il segmento IL non produce trigrammi;
- NERO produce NER, ERO;
- non compaia ILN o LNE.

16. test_continuous_counts_base25_valid_cross_word

Input:

"IL KATTO NERO"

Con alphabet_25.

Tutte le parole sono valide.

Segmento continuous:
ILKATTONERO

Verificare che:
- venga generato il trigramma cross-word ILK;
- K sia codificata come 9;
- nessun ID venga calcolato con base 26.

Calcolo ILK:
I=8, L=10, K=9

id = ((8 * 25) + 10) * 25 + 9
id = 5259

Verificare:

ngram_to_id("ILK", alphabet_25) == 5259
Counter continuous[3][5259] == 1

17. test_npy_shapes_base25

Eseguire il builder su fixture piccola con:

alphabet = ABCDEFGHIKLMNOPQRSTUVWXYZ
min_n = 3
max_n = 4
save_npy = true

Verificare:

paisa_3grams_inword_logprob.npy.shape == (25^3,) == (15625,)
paisa_4grams_inword_logprob.npy.shape == (25^4,) == (390625,)
paisa_3grams_continuous_logprob.npy.shape == (15625,)
paisa_4grams_continuous_logprob.npy.shape == (390625,)
paisa_letter_counts.npy.shape == (25,)
paisa_letter_frequencies.npy.shape == (25,)
paisa_letter_logprob.npy.shape == (25,)

18. test_metadata_base25

Eseguire il builder su fixture piccola con alphabet_25.

Verificare che metadata.json contenga:

"alphabet": "ABCDEFGHIKLMNOPQRSTUVWXYZ"
"base": 25
"invalid_word_policy": "drop-word"

Per i modelli:

"3_inword": {
  "vocab_size": 15625
}

"4_inword": {
  "vocab_size": 390625
}

"3_continuous": {
  "vocab_size": 15625
}

"4_continuous": {
  "vocab_size": 390625
}

Per lettere:

total_letters > 0
unique_letters <= 25

19. test_letter_counts_base25_no_j_and_no_j_to_i

Input fixture con testo:

"J I K JAZZ KILO"

Con alphabet_25 e invalid-word-policy=drop-word.

Parole valide:
I
K
KILO

Parole scartate:
J
JAZZ

Atteso:
- J non viene contata;
- JAZZ non viene contata;
- I viene contata solo per la parola I e per KILO se contiene I;
- K viene contata per K e KILO;
- nessun conteggio artificiale di I dovuto a J.

Verificare:
- letter_counts[8] corrisponde solo alle I realmente presenti in parole valide;
- letter_counts[9] corrisponde alle K realmente presenti;
- sum(letter_counts) corrisponde alla somma delle lunghezze delle sole parole valide.

20. test_letter_frequencies_base25_sum_to_one

Dopo generazione con alphabet_25:

Verificare:

sum(letter_frequencies) ≈ 1.0

e che:

len(letter_frequencies) == 25

21. test_no_hardcoded_26_in_shapes

Eseguire builder con alphabet_25.

Verificare che nessun array generato abbia shape:
17576
456976
26

Gli array devono essere:
15625
390625
25

22. test_readme_generated_model_mentions_base25_and_drop_word_policy

Se README_GENERATED_MODEL.md viene generato con alphabet_25, verificare che contenga:

- alphabet: ABCDEFGHIKLMNOPQRSTUVWXYZ
- base: 25
- trigram vocabulary size: 15625
- quadrigram vocabulary size: 390625
- letter array size: 25
- invalid word policy: drop-word
- spiegazione che le parole contenenti J vengono escluse, non convertite in I.

23. test_parallel_equals_sequential_base25

Se il builder supporta multiprocessing:

Eseguire sulla stessa fixture con:
- workers=1
- workers=2

Usando alphabet_25.

Verificare che:
- counts inword 3 identici;
- counts inword 4 identici;
- counts continuous 3 identici;
- counts continuous 4 identici;
- letter_counts identici;
- metadata coerente, salvo campi execution mode/workers.

REGOLE DI IMPLEMENTAZIONE DA VERIFICARE

Il codice deve usare sempre:

base = len(alphabet)

Tutte le seguenti parti devono dipendere da base:

- ngram_to_id;
- id_to_ngram;
- vocab_size = base ** n;
- dimensioni array NPY;
- letter_counts;
- letter_frequencies;
- letter_logprob;
- range delle lettere;
- validazione metadata;
- README_GENERATED_MODEL.md;
- test di collisione.

La normalizzazione deve filtrare parole rispetto all’alfabeto scelto.

Con alphabet_25:
- J non è ammessa;
- K è ammessa;
- tutte le lettere dopo J non devono essere shiftate;
- le parole contenenti J devono essere scartate interamente;
- J non deve mai essere convertita in I.

CRITERI DI ACCETTAZIONE

Il supporto ad alfabeto 25 senza J è corretto solo se:

1. alphabet_25 viene accettato via --alphabet;
2. base viene calcolata come 25;
3. J non compare nella mappa carattere->intero;
4. K viene mappata a 9, non a 10;
5. Z viene mappata a 24, non a 25;
6. ngram_to_id usa base 25;
7. id_to_ngram usa base 25;
8. gli array NPY hanno shape 25^n;
9. gli array lettere hanno shape 25;
10. metadata.json riporta base=25;
11. metadata.json riporta invalid_word_policy=drop-word;
12. README_GENERATED_MODEL.md documenta base=25;
13. README_GENERATED_MODEL.md documenta che le parole con J sono escluse;
14. J non viene mai convertita in I;
15. le parole contenenti J non contribuiscono né a inword né a continuous;
16. le parole contenenti J interrompono i segmenti continuous;
17. tutti i test a 26 caratteri già esistenti continuano a passare;
18. tutti i nuovi test a 25 caratteri passano.