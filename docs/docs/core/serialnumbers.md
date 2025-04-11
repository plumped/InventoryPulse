# Seriennummernverwaltung

Die Seriennummernverwaltung erlaubt Ihnen, einzelne Produkte über ihre gesamte Lebensdauer zu verfolgen. Diese Funktion ist besonders nützlich für hochwertige Geräte, elektronische Komponenten oder medizinische Produkte.

## Übersicht

Mit der Seriennummernverwaltung in InventoryPulse können Sie:

- Eindeutige Seriennummern für Produkte erfassen
- Den Lebenszyklus und Standort jedes einzelnen Artikels verfolgen
- Lagerverschiebungen für spezifische Artikel durchführen
- Verfallsdaten für Artikel mit begrenzter Haltbarkeit überwachen
- Historie und Bewegungen jeder Seriennummer einsehen
- Seriennummern über Barcode-Scanner schnell erfassen

## Seriennummern aktivieren

Bevor Sie Seriennummern verwenden können, müssen Sie diese Funktion für das entsprechende Produkt aktivieren:

1. Navigieren Sie zur Produktdetailseite
2. Klicken Sie auf "Bearbeiten"
3. Aktivieren Sie die Option "Hat Seriennummern"
4. Speichern Sie die Änderungen

!!! note "Hinweis"
    Sobald ein Produkt Seriennummern hat, kann diese Funktion nicht mehr deaktiviert werden. Falls Sie die Funktion für ein vorhandenes Produkt aktivieren, müssen Sie möglicherweise den aktuellen Bestand anpassen.

## Seriennummern hinzufügen

Es gibt mehrere Möglichkeiten, Seriennummern hinzuzufügen:

### Einzelne Seriennummer hinzufügen

1. Gehen Sie zur Produktdetailseite
2. Klicken Sie auf den Tab "Seriennummern"
3. Klicken Sie auf "Neue Seriennummer"
4. Füllen Sie das Formular aus:
   - Seriennummer (eindeutige ID)
   - Status (z.B. "Auf Lager", "Verkauft", "Defekt")
   - Lager (aktueller Standort)
   - Optional: Kaufdatum, Ablaufdatum, Notizen
5. Klicken Sie auf "Speichern"

### Mehrere Seriennummern auf einmal hinzufügen

Für größere Mengen an Seriennummern bietet InventoryPulse eine Masseneingabe-Funktion:

1. Gehen Sie zur Produktdetailseite
2. Klicken Sie auf den Tab "Seriennummern"
3. Wählen Sie "Massenerfassung"
4. Geben Sie die folgenden Informationen ein:
   - Präfix (optional, z.B. "SN-")
   - Startnummer (z.B. 1001)
   - Anzahl (z.B. 50 für SN-1001 bis SN-1050)
   - Anzahl der Stellen (z.B. 6 für SN-001001)
   - Gemeinsame Eigenschaften: Status, Lager, Datum etc.
5. Klicken Sie auf "Seriennummern erstellen"

!!! warning "Achtung"
    Das System prüft automatisch, ob Seriennummern bereits existieren, und vermeidet Duplikate. Eine Fehlermeldung wird angezeigt, wenn Konflikte auftreten.

### Seriennummern importieren

Für die Integration mit externen Systemen oder Massenimport:

1. Navigieren Sie zu "Import" → "Seriennummern importieren"
2. Laden Sie eine CSV-Datei mit den erforderlichen Spalten hoch
3. Konfigurieren Sie die Import-Optionen
4. Starten Sie den Import

Die CSV-Datei sollte mindestens folgende Spalten enthalten:

```csv
product_sku,serial_number,status,warehouse_name
P1001,SN12345,in_stock,Hauptlager
P1001,SN12346,in_stock,Hauptlager
```

Weitere Details finden Sie im Abschnitt [CSV-Import](../data/csv-import.md).

## Seriennummern verwalten

### Übersicht aller Seriennummern

Die zentrale Seriennummern-Übersicht erreichen Sie über:

1. Hauptmenü → "Produkte" → "Seriennummern-Übersicht"

Hier können Sie:

- Alle Seriennummern im System sehen
- Nach Produkt, Status, Lager oder Seriennummer filtern
- Detailansichten aufrufen
- Massenaktionen durchführen

![Seriennummern-Übersicht](../assets/screenshots/serialnumber-list.png)

### Seriennummerndetails ansehen

Um die Details einer Seriennummer einzusehen:

1. Klicken Sie in der Seriennummern-Liste auf die gewünschte Seriennummer
2. Oder nutzen Sie die Funktion "Seriennummer scannen" im Menü und scannen Sie den Barcode

Die Detailansicht zeigt:

- Grundinformationen (Produkt, Status, Standort)
- Zeitstempel (Erstellung, letzte Änderung)
- QR-Code für schnelles Scannen
- Verlaufsdaten
- Verfügbare Aktionen

### Seriennummern-Status ändern

Um den Status einer Seriennummer zu ändern:

1. Öffnen Sie die Seriennummer-Detailansicht
2. Klicken Sie auf "Bearbeiten"
3. Ändern Sie den Status im Dropdown-Menü
4. Speichern Sie die Änderungen

Verfügbare Status sind:

- **Auf Lager**: Artikel ist verfügbar
- **Verkauft**: Artikel wurde verkauft
- **In Benutzung**: Artikel wird aktiv verwendet
- **Defekt**: Artikel ist beschädigt
- **Zurückgegeben**: Artikel wurde zurückgegeben
- **Entsorgt**: Artikel wurde entsorgt
- **Reserviert**: Artikel ist reserviert
- **In Reparatur**: Artikel wird repariert

### Seriennummern transferieren

Um eine Seriennummer von einem Lager zu einem anderen zu verschieben:

1. Gehen Sie zu "Produkte" → "Seriennummer transferieren"
2. Scannen oder geben Sie die Seriennummer ein
3. Wählen Sie das Ziellager
4. Optional: Fügen Sie Notizen hinzu
5. Klicken Sie auf "Transferieren"

![Seriennummer transferieren](../assets/screenshots/serialnumber-transfer.png)

## Seriennummern scannen

Das Scannen von Seriennummern ist eine effiziente Methode, um:

1. Schnell Informationen zu einer Seriennummer zu erhalten
2. Bestände zu überprüfen
3. Lagerverschiebungen durchzuführen

### Scanvorgang:

1. Gehen Sie zu "Produkte" → "Seriennummer scannen"
2. Platzieren Sie den Cursor im Eingabefeld
3. Scannen Sie den Barcode mit einem Barcode-Scanner
   - Alternativ können Sie die Seriennummer manuell eingeben
4. Das System zeigt automatisch die Detailseite der gescannten Seriennummer

!!! tip "Tipp"
    Für optimale Ergebnisse empfehlen wir die Verwendung eines USB-Barcode-Scanners, der als HID-Gerät (Human Interface Device) funktioniert und keine zusätzliche Treiber-Installation erfordert.

## Seriennummern exportieren

Um Seriennummern zu exportieren:

1. Gehen Sie zu "Produkte" → "Seriennummern exportieren"
2. Wählen Sie die gewünschten Filter (Produkt, Status, Lager etc.)
3. Wählen Sie das Exportformat (CSV, Excel, PDF)
4. Wählen Sie die zu exportierenden Felder
5. Klicken Sie auf "Export starten"

Der Export enthält alle gefilterten Seriennummern mit den ausgewählten Feldern.

## Verfallsdatenverwaltung

Für Produkte mit begrenzter Haltbarkeit bietet InventoryPulse eine Verfallsdatenverwaltung:

1. Aktivieren Sie "Hat Verfallsverfolgung" bei den Produkteinstellungen
2. Geben Sie bei der Seriennummernerstellung das Ablaufdatum ein
3. Nutzen Sie die "Verfallsdaten"-Übersicht im Menü, um:
   - Abgelaufene Artikel zu identifizieren
   - Bald ablaufende Artikel zu überwachen
   - Aktionen zu planen

!!! warning "Wichtig"
    Die Verfallsdatenverfolgung erfordert, dass entweder die Seriennummern- oder die Chargenverfolgung aktiviert ist.

## Fehlerbehebung

### Häufige Probleme

**Duplikate bei der Seriennummern-Erstellung**

Das System verhindert die Erstellung von Duplikaten. Wenn Sie eine Fehlermeldung erhalten, überprüfen Sie, ob die Seriennummer bereits existiert.

**Seriennummer wird nicht gefunden beim Scannen**

Stellen Sie sicher, dass:
- Die Seriennummer korrekt erfasst wurde
- Die Seriennummer im System existiert
- Sie ausreichende Berechtigungen haben

**Seriennummernverwaltung kann nicht deaktiviert werden**

Sobald ein Produkt Seriennummern hat, kann diese Funktion nicht mehr deaktiviert werden. Sie müssten ein neues Produkt ohne Seriennummernverwaltung anlegen.

## Best Practices

- Verwenden Sie ein konsistentes Benennungsschema für Seriennummern
- Nutzen Sie die Masseneingabe für größere Mengen
- Führen Sie regelmäßige Audits mit Hilfe der Scan-Funktion durch
- Verwenden Sie aussagekräftige Notizen für besondere Umstände
- Schulen Sie alle Benutzer in der korrekten Seriennummernerfassung