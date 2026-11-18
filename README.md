# Mobvoi Home Treadmill Plus — Natywna integracja Home Assistant

Natywna integracja Bluetooth (FTMS) do bezpośredniej obsługi bieżni **Mobvoi Home Treadmill Plus** w Home Assistant z poziomu panelu UI (*Config Flow* — bez ręcznego edytowania YAML i osobnych skryptów).

## Instalacja (przez HACS lub ręcznie)

### Sposób 1: Przez własne repozytorium HACS (zero wgrywania pojedynczych plików)
1. Wrzuć zawartość tego archiwum na swoje konto GitHub (jako nowe publiczne repozytorium).
2. W Home Assistant otwórz **HACS** → **Integracje** → menu trzech kropek w prawym górnym rogu → **Niestandardowe repozytoria**.
3. Wklej adres swojego repozytorium na GitHubie i wybierz kategorię **Integracja**.
4. Kliknij **Pobierz** i zrestartuj Home Assistant.

### Sposób 2: Rozpakowanie archiwum
1. Rozpakuj folder `mobvoi_treadmill` do katalogu `/config/custom_components/mobvoi_treadmill` w Home Assistant.
2. Zrestartuj Home Assistant.

## Konfiguracja w Home Assistant
1. Włącz bieżnię Mobvoi (musi być w zasięgu Bluetooth Twojego Mini PC).
2. W Home Assistant wejdź w **Ustawienia** → **Urządzenia oraz usługi**.
3. Bieżnia powinna zostać wykryta automatycznie u góry ekranu. Jeśli nie, kliknij **+ Dodaj integrację**, wyszukaj **Mobvoi Home Treadmill Plus** i wybierz ją z listy.
4. Po dodaniu otrzymasz gotowe urządzenie z encjami:
   - `sensor.mobvoi_home_treadmill_plus_predkosc` (km/h)
   - `sensor.mobvoi_home_treadmill_plus_dystans` (m)
   - `sensor.mobvoi_home_treadmill_plus_kalorie` (kcal)
   - `sensor.mobvoi_home_treadmill_plus_czas_treningu` (s)
   - `button.mobvoi_home_treadmill_plus_start` / `stop`
   - `number.mobvoi_home_treadmill_plus_predkosc_docelowa` (suwak 1.0–12.0 km/h)
