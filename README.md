# TON NFT Bot - Migrazione a Pytoniq

## Modifiche Principali

### ✅ Da `pytonlib` a `pytoniq`

**Vantaggi:**
- 🚀 Più stabile e moderno
- 🔄 Gestione automatica dei lite servers
- 🛡️ Migliore gestione degli errori di rete
- ⚡ Performance migliorate

### 📋 File Modificati

1. **requirements.txt** - Sostituito `pytonlib` con `pytoniq` e `pytoniq-core`
2. **main.py** - Riscritto completamente per usare `LiteBalancer`
3. **nftData.py** - Adattato per pytoniq (parsing Cell/Slice)
4. **functions.py** - Aggiornato parsing stack e indirizzi

### 🔧 Caratteristiche Chiave

#### Client Globale con LiteBalancer
```python
from pytoniq import LiteBalancer

client = LiteBalancer.from_mainnet_config(trust_level=2)
await client.start_up()
```

- Si connette automaticamente a più lite servers
- Bilancia il carico tra di essi
- Riprova automaticamente in caso di errori

#### Parsing Migliorato
- Conversione automatica da stack pytoniq a formato compatibile
- Gestione robusta di Cell, Slice, Address
- Fallback su metodi alternativi in caso di errore

#### Gestione Errori
- Timeout aumentati (60s)
- Retry automatici per richieste fallite
- Log dettagliati per debugging

## 🚀 Deploy su Render

### Variabili d'Ambiente Richieste

```bash
BOT_TOKEN=your_telegram_bot_token
NOTIFY_CHAT=your_chat_id
CMC_TOKEN=your_coinmarketcap_token  # Opzionale
```

### Build Command
```bash
pip install -r requirements.txt
```

### Start Command
```bash
python main.py
```

### Health Check
Il bot espone un endpoint HTTP sulla porta definita da `PORT` (default: 8000):
```
GET / → "OK - TON NFT Bot Alive"
```

## 📝 Differenze Principali nel Codice

### Vecchio (pytonlib)
```python
client = TonlibClient(ls_index=2, config=config, ...)
await client.init()
trs = await client.get_transactions(account=address, limit=50)
```

### Nuovo (pytoniq)
```python
client = LiteBalancer.from_mainnet_config(trust_level=2)
await client.start_up()
trs = await client.get_transactions(address=Address(address), count=50)
```

### Parsing Transazioni

**Vecchio:**
```python
sc_address = tr['in_msg']['source']
```

**Nuovo:**
```python
in_msg = tr.in_msg
sc_address = in_msg.info.src.to_str(1, 1, 1)
```

### Run Get Method

**Vecchio:**
```python
response = await client.raw_run_method(
    address=sc_address,
    method='get_sale_data',
    stack_data=[]
)
```

**Nuovo:**
```python
response = await client.run_get_method(
    address=sc_address,
    method='get_sale_data',
    stack=[]
)
```

## 🐛 Risoluzione Problemi

### Errore: `LITE_SERVER_NETWORK`
✅ **RISOLTO** - pytoniq gestisce automaticamente la connessione a lite servers multipli

### Errore: `module 'tvm_valuetypes' not found`
✅ **RISOLTO** - Rimosso da requirements.txt (non necessario con pytoniq)

### Timeout sulle richieste
✅ **MIGLIORATO** - Timeout aumentato a 60s + retry automatici

## 🔍 Testing Locale

```bash
# Installa le dipendenze
pip install -r requirements.txt

# Crea file .env
echo "BOT_TOKEN=your_token" > .env
echo "NOTIFY_CHAT=your_chat_id" >> .env

# Avvia il bot
python main.py
```

## 📊 Monitoraggio

Il bot stampa log dettagliati:
```
[INIT] Creating global LiteBalancer client...
[INIT] Global LiteBalancer client created successfully.
[CYCLE #1] Start at 10:30:45
[royalty_trs] Trovate 10 transazioni per vwLHL0
[CYCLE #1] Updated lastUtime: 1738234567
[CYCLE #1] Finished. Sleeping 15s...
```

## ⚠️ Note Importanti

1. **lastUtime.txt** deve esistere nella root del progetto (creato automaticamente se mancante)
2. Le variabili d'ambiente sono **obbligatorie** su Render
3. Il bot cicla ogni 15 secondi (modificabile in `main.py`)
4. Il limite transazioni è 50 per chiamata (configurabile in `config.py`)

## 📚 Documentazione Pytoniq

- GitHub: https://github.com/yungwine/pytoniq
- Docs: https://pytoniq.readthedocs.io/

## 🆘 Supporto

Se riscontri errori:
1. Controlla i log su Render
2. Verifica le variabili d'ambiente
3. Controlla che `lastUtime.txt` esista e sia valido
4. Verifica la connettività di rete
