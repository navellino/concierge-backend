# 🧠 Smart Concierge AI – Project Overview

## 📋 Descrizione generale
Il progetto **Smart Concierge AI** è un backend sviluppato in **Python (FastAPI)** con integrazione a **Google Sheets** che fornisce un assistente intelligente per host di case vacanza.  
L'obiettivo è creare un concierge digitale capace di:
- rispondere automaticamente alle domande degli ospiti,
- personalizzare le risposte in base ai dati della prenotazione,
- contestualizzare le informazioni in base a **stagione**, **ora del giorno** e **lingua dell’ospite**,
- ridurre al minimo i costi d’uso dell’AI e azzerare la dipendenza dal web scraping.

---

## 🏗️ Architettura attuale

### Backend
- **Framework:** FastAPI + Uvicorn  
- **Database:** Google Sheets (via `gspread`)
- **AI Engine:** OpenAI GPT-4o-mini (solo per generazione linguistica, nessuna ricerca web)
- **Knowledge base:** `conoscenza.txt`  
  - File di testo gestito dagli host.  
  - Contiene informazioni strutturate con tag `@property:` e `@lang:` (es. WIFI, CHECKIN, CHECKOUT, RISTORANTI, ecc.)
- **SMTP Integration:** invio automatico email (Aruba o altri provider)
- **Rate Limiting:** pianificato, max 8 chiamate AI per ospite.

### Struttura directory
```
app/
 ├── main.py
 ├── config.py
 ├── routers/
 │    ├── booking.py      # Gestione prenotazioni, autorizzazioni e email host
 │    └── chat.py         # Gestione chatbot, AI e knowledge base
 └── services/
      ├── sheets.py       # Connessione e logica Google Sheets
      ├── mail.py         # Invio email SMTP
      ├── templates.py    # Template email di attivazione concierge
      ├── kb.py           # Parser e gestore knowledge base locale
      └── ai.py           # Client OpenAI e costruzione prompt
.env
conoscenza.txt
```

---

## ✅ Funzionalità già implementate

### 🔧 Sistema di base
- Creazione del backend FastAPI funzionante.
- Connessione stabile a Google Sheets tramite service account.
- Lettura e scrittura dei dati (append, update, match, upsert).
- Gestione dei file `.env` con chiavi e configurazioni.

### 👤 Gestione ospiti
- `/api/guest/register` → aggiunge o aggiorna prenotazioni in `Bookings`.
- `/api/match-guest` → riconosce l’ospite in base a data + cognome (+ nome opzionale).

### 👨‍💼 Gestione host
- `/api/host/authorize` → autorizza ospite, imposta codice check-in e Wi-Fi, invia email automatica di conferma.

### 🧠 Chatbot intelligente
- `/api/chat` → risponde alle richieste dell’ospite:
  - Regole fisse (Wi-Fi, check-in/out, codice porta, emergenze, ristoranti, mare, parcheggio).
  - Contesto: stagione, ora del giorno, lingua, dati prenotazione.
  - AI come “parlatore” naturale → GPT-4o-mini.
  - Nessuna ricerca web: usa solo `conoscenza.txt`.

### ✉️ Notifiche automatiche
- Email di conferma concierge con template multilingua.

---

## 🚀 Prossimi step

### 🪶 Step 1 – Logging conversazioni
- Tab “Logs” su Google Sheet.
- Scrittura automatica di ogni scambio chatbot:
  - timestamp, property_id, ospite, domanda, risposta, used_ai.
- Analisi statistica e miglioramento `conoscenza.txt`.

### 🧱 Step 2 – Rate limit AI
- Colonna `ai_calls` in tab `Bookings`.
- Ogni chiamata AI incrementa il contatore.
- Dopo 8 → blocco automatico con messaggio tipo:
  > “Per ulteriori domande ti metto in contatto con l’host.”

### 🧩 Step 3 – Prompt rigido
- Impedire all’AI di:
  - fornire codici o password senza autorizzazione;
  - inventare servizi non presenti nel `conoscenza.txt`.
- Migliorare coerenza linguistica e tono di voce.

### 💬 Step 4 – Widget front-end
- Piccolo componente JS per integrare la chat nel sito web dell’host.
- Interfaccia responsive stile “bubble chat”.

### 📊 Step 5 – Mini dashboard host
- Endpoint `/api/logs` per visualizzare le ultime conversazioni.
- Pannello HTML con autenticazione leggera per gestire le proprietà.

---

## 🔒 Obiettivi finali

- Concierge completamente **self-hosted e sicuro**.
- **Multi-lingua** automatica (IT, EN, ES).
- **Zero costi fissi** tranne l’uso AI minimo.
- **Aggiornabile dagli host** tramite un semplice file `conoscenza.txt`.
- Pronto per deploy su **Render** o su server personale (insieme a Veely).

---

## 🧭 Prossimi file da creare
| File | Descrizione |
|------|--------------|
| `app/services/logger.py` | Scrive i log delle conversazioni in Google Sheet |
| `app/routers/logs.py` | Endpoint per leggere i log e filtrarli per host |
| `public/widget.html` | Interfaccia chat integrabile nei siti |
| `public/styles.css` | Stile base del widget |
| `app/auth.py` | Autenticazione semplice (JWT o API key host) |

---

## ✨ In sintesi
Il progetto ha ora un **backend modulare, scalabile e già utile**:  
può riconoscere ospiti, gestire autorizzazioni, rispondere alle domande e inviare email automatiche.  
I prossimi passi renderanno il concierge **autonomo, tracciabile e pronto alla produzione.**

---

> Ultimo aggiornamento: novembre 2025  
> Autore: Nicola Avellino  
> Progetto: Smart Concierge AI
