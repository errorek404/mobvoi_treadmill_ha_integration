# Mobvoi Home Treadmill Plus - Integracja Home Assistant (v1.2.0)

## Co nowego w wersji 1.2.0?
1. **Przycisk Power (`switch.mobvoi_power`)** – wybudza wyświetlacz i elektronikę bieżni ze stanu uśpienia (wysyłając komendę *Request Control* `0x00` po Bluetooth FTMS) bez natychmiastowego ruszania pasa. Wyłączenie przełącznika zatrzymuje pas i przełącza bieżnię w stan czuwania.
2. **Przełącznik Start Pasa (`switch.mobvoi_start_pasa`)** – osobny przełącznik do uruchamiania i zatrzymywania samego pasa biegowego.
3. **Gotowy Dashboard (`dashboard.yaml`)** – kompletny widok z kafelkami Power, Start/Stop, parametrami na żywo, suwakiem prędkości, 4 presetami oraz wykresem.

## Jak wgrać Dashboard w Home Assistant?
1. W Home Assistant przejdź do **Ustawienia** -> **Dashboardy** -> **Dodaj dashboard** (np. o nazwie *Bieżnia*).
2. Otwórz nowy dashboard, kliknij **ikonę ołówka (Edytuj dashboard)** w prawym górnym rogu.
3. Kliknij **trzy kropki** w prawym górnym rogu -> **Edytor surowej konfiguracji (Raw configuration editor)**.
4. Wklej zawartość pliku `dashboard.yaml` i kliknij **Zapisz**.
