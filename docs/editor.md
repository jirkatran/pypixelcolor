# Webový editor 96 × 16

Z kořenové složky projektu:

```bash
source .venv/bin/activate
python -m pypixelcolor.editor -a C54AE0FD-CD75-3956-1852-F3FC94ECD6BA
```

Otevři http://localhost:8765. Server ukončíš Ctrl+C. Jiný port nastavíš přes `--port 8766`.
V části **03 / Tvůj panel** klikni na **Vyhledat bannery**. Po 6 sekundách
vyber nalezený panel ze seznamu a klikni na **Připojit**. Adresu lze také zadat
ručně. Uložené panely zůstávají v seznamu i po obnovení stránky; označení „uložený“
neznamená, že jsou právě v dosahu. Připojený panel může při hledání chybět, protože
již neinzeruje. Stav spojení se kontroluje každých 5 sekund.

Spojení zůstává otevřené do **Odpojit**, přepnutí na jiný panel nebo ukončení serveru.
Odeslat použije vždy adresu právě vybraného panelu; pokud je připojený jiný, server
jej odpojí a připojí vybraný. Editor podporuje jedno aktivní spojení současně.

Na macOS povol Bluetooth aplikaci, ze které server spouštíš.

Editor podporuje text (včetně znaků dostupných v systémovém písmu), barvu a velikost
písma, zarovnání, kreslení, gumu, historii zpět, import statického obrázku, PNG export
a projekty JSON. Náhled i odesílaný PNG mají vždy 96 × 16 pixelů. Dlouhý text se
na okrajích ořízne; editor na přesah upozorní. Tato verze vytváří statické bannery.
Návrh se průběžně ukládá do localStorage prohlížeče. Projekty lze stáhnout do souboru.
Úpravy textu znovu vykreslí celé plátno.

## Propojení s BAZARem

Webové soubory jsou v `src/pypixelcolor/editor/`. Editor nemá framework ani CDN
závislosti. BAZAR může převzít rozhraní nebo jeho backend může volat lokální API.
BLE zajišťuje Python na počítači v dosahu panelu. Samotný hosting v cloudu nemůže
používat Bluetooth tohoto Macu.

`GET /api/config` vrací výchozí adresu panelu a rozměry.

`POST /api/send` přijímá JSON:

```json
{
  "address": "C54AE0FD-CD75-3956-1852-F3FC94ECD6BA",
  "image": "data:image/png;base64,..."
}
```

`image` je PNG přesně 96 × 16 px (například `canvas.toDataURL('image/png')`).
`address` může chybět, pokud byla zadána při startu serveru.
Úspěch: HTTP 200, `{"ok": true, "message": "Banner byl odeslán do panelu."}`.
Další endpointy (POST, JSON):

- `/api/scan` s `{}`: seznam `devices` obsahující `name` a `address`.
- `/api/connect` s `{"address":"UUID nebo MAC"}`: připojení a kontrola rozměrů.
- `/api/disconnect` s `{}`: odpojení aktivního panelu.
- `/api/status` s `{}`: aktuální `connected` a `address`.

Bluetooth odpovědi obsahují `ok`, `connected` a adresu aktivního spojení.
Chyby: 400 neplatný vstup, 409 probíhající operace, 502 chyba Bluetooth nebo
nepotvrzený přenos, 503 nedostupný Bluetooth proces. Operace jsou serializované
a mají časový limit. Spojení je společné pro všechny karty editoru.

Server poslouchá pouze na 127.0.0.1 a odmítá cizí Host/Origin. Pro integraci použij
volání z backendu BAZARu na stejném počítači nebo jeho autentizovanou reverzní proxy.
Přímé volání z webu na jiné doméně není zapnuté. Pro vzdálené nasazení bude třeba
navrhnout autentizovaný most mezi BAZAR serverem a počítačem s Bluetooth.

## Posun textu doleva

V části 01 nastav **Pohyb textu → Posun doleva (shift)** a rychlost 1–100.
Panel přehrává celý text sám, i po odpojení počítače. Používá výchozí písmo
16 px a černé pozadí; toto nastavení bylo ověřeno uživatelem na LED_BLE_4ACB8622.
Vlastní velikost písma, pozadí, kresba, obrázky a zarovnání se v tomto režimu
nepoužijí. Náhled písma a časování je orientační. PNG export je statické plátno.
Pohyb i rychlost se ukládají v projektu JSON.

API: `POST /api/send` s JSON:

```json
{
  "address": "UUID nebo MAC",
  "animation": "scroll_left",
  "text": "AHOJ SVETE",
  "speed": 80,
  "size": 16,
  "color": "#ffffff",
  "background": "#000000"
}
```

V posunu se velikost a pozadí nepřenášejí; server používá ověřené výchozí hodnoty.
Pro statický banner vynech `animation` nebo nastav `static` a pošli `image`.
