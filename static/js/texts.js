// Texts in Croatian and English, plural rules and joining lists of units.
// Shared through the BC namespace; loaded before app.js (see templates/index.html).
(function (BC) {
    'use strict';

    // Croatian forms: [1, 21, 31…], [2–4, 22–24…], [0, 5–20, 25–30…]
    const FORMS = {
        year: ['godina', 'godine', 'godina'],
        month: ['mjesec', 'mjeseca', 'mjeseci'],
        week: ['tjedan', 'tjedna', 'tjedana'],
        day: ['dan', 'dana', 'dana'],
        hour: ['sat', 'sata', 'sati'],
        minute: ['minuta', 'minute', 'minuta'],
        second: ['sekunda', 'sekunde', 'sekundi'],
    };

    function plural(n, forms) {
        const mod10 = n % 10;
        const mod100 = n % 100;
        if (mod10 === 1 && mod100 !== 11) return forms[0];
        if (mod10 >= 2 && mod10 <= 4 && !(mod100 >= 12 && mod100 <= 14)) return forms[1];
        return forms[2];
    }

    const MONTH_NAMES_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const MONTH_NAMES_DE = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September',
        'Oktober', 'November', 'Dezember'];
    const MONTH_NAMES_IT = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto',
        'settembre', 'ottobre', 'novembre', 'dicembre'];
    // German and Italian: [singular, plural]
    const WORDS_DE = {
        year: ['Jahr', 'Jahre'], month: ['Monat', 'Monate'], week: ['Woche', 'Wochen'], day: ['Tag', 'Tage'],
        hour: ['Stunde', 'Stunden'], minute: ['Minute', 'Minuten'], second: ['Sekunde', 'Sekunden'],
    };
    const WORDS_IT = {
        year: ['anno', 'anni'], month: ['mese', 'mesi'], week: ['settimana', 'settimane'], day: ['giorno', 'giorni'],
        hour: ['ora', 'ore'], minute: ['minuto', 'minuti'], second: ['secondo', 'secondi'],
    };
    const pad = (n) => String(n).padStart(2, '0');

    function ordinalEn(n) {
        const suffix = n % 100 >= 11 && n % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th');
        return `${n}${suffix}`;
    }

    // All texts shown by the script. Page texts are in i18n.py.
    const TEXT = {
        hr: {
            word: (n, key) => plural(n, FORMS[key]),
            and: 'i',
            today: 'danas',
            tomorrow: 'sutra',
            inDays: (n) => `za ${unit(n, 'day', 'hr')}`,
            ago: (n) => `prije ${unit(n, 'day', 'hr')}`,
            birthday: (y) => `${y}. rođendan`,
            pregnancyMilestone: {
                second: '2. tromjesečje', half: 'Polovica trudnoće', third: '3. tromjesečje',
                term: 'Donošena trudnoća', due: 'Termin poroda',
            },
            date: (d) => `${pad(d.getUTCDate())}.${pad(d.getUTCMonth() + 1)}.${d.getUTCFullYear()}.`,
            at: 'u',
            child: (n) => `Dijete ${n}`,
            childAgeHeading: 'Dob djeteta',
            born: 'Rođenje',
            age: 'Dob',
            or: 'odnosno',
            pregnancy: 'Trudnoća',
            dueDate: 'Termin',
            pregnancyDetail: (s) => `${s.weeks}+${s.weekDays} · ${s.week}.\u00a0tjedan · ${s.trimester}.\u00a0tromjesečje`,
            week: (n) => `${n}. tjedan`,
            progress: (percent) => `${percent} % trudnoće`,
            dateLabel: {
                lmp: 'Prvi dan zadnje menstruacije', due: 'Termin poroda',
                ivf: 'Datum transfera zametka', ultrasound: 'Datum ultrazvuka',
            },
            errors: {
                birthMissing: 'Unesite datum rođenja.',
                birthInvalid: 'Neispravan datum ili vrijeme rođenja.',
                birthFuture: 'Datum rođenja ne može biti u budućnosti. Za trudnoću odaberite „Trudnoća”.',
                dateMissing: 'Unesite datum.',
                dateInvalid: 'Neispravan datum.',
                lmpFuture: 'Datum zadnje menstruacije ne može biti u budućnosti.',
                dueInvalid: 'Neispravan termin poroda.',
                dueTooLate: 'Termin poroda može biti najviše 20 tjedana nakon rođenja.',
                dateFuture: 'Datum ne može biti u budućnosti.',
                pregnancyTooOld: 'Prema ovim podacima trudnoća traje više od 42 tjedna. Ako je beba rođena, odaberite „Beba”.',
                gestationInvalid: 'Unesite tjedne (0–42) i dane (0–6) s ultrazvuka.',
                dueTooFar: 'Termin je predaleko u budućnosti (više od 40 tjedana).',
                lmpTooOld: 'Zadnja menstruacija je prije više od 42 tjedna. Ako je beba rođena, odaberite „Beba”.',
                duePassed: 'Termin je prošao prije više od dva tjedna. Ako je beba rođena, odaberite „Beba”.',
            },
            linkCopied: 'Poveznica je kopirana.',
            textCopied: 'Tekst je kopiran.',
            pictureSaved: 'Slika je spremljena.',
            pictureFailed: 'Izrada slike nije uspjela.',
            copyFailed: 'Kopiranje nije uspjelo.',
            childRemoved: (label) => `Uklonjeno: „${label}”.`,
            // Croatian dates already end with a full stop ("10.04.2026.")
            measurementRemoved: (date) => `Uklonjeno: mjerenje od ${date}${date.endsWith('.') ? '' : '.'}`,
            undo: 'Poništi',
            lastBackup: (date) => `Zadnja sigurnosna kopija: ${date}`,
            lastBackupNever: 'Zadnja sigurnosna kopija: još nijedna',
            corrected: 'Korigirana dob',
            correctedNotNeeded: 'Nije potrebna',
            correctedStarts: 'Počinje na termin',
            correctedStartsIn: (when, due) => `${when} (termin ${due})`,
            gestationAtBirth: (w, d) => `Gestacijska dob pri rođenju:\u00a0${w}+${d}`,
            correctedUntil2: 'Korekcija se obično koristi do 2. godine.',
            backupRestored: 'Podaci su učitani.',
            backupNothingNew: 'Nema novih podataka – sve je već bilo spremljeno.',
            backupInvalid: 'Ovo nije ispravna sigurnosna kopija.',
            backupTooLarge: 'Datoteka je prevelika za sigurnosnu kopiju.',
            backupLinkCopied: 'Poveznica za prijenos je kopirana.',
            backupReplacePregnancy: 'Sigurnosna kopija ima druge podatke o trudnoći. Zamijeniti postojeće?',
            measures: { weight: 'Težina', length: 'Duljina', head: 'Opseg glave' },
            growthChartLabel: (label) => `Krivulja rasta: ${label}, percentili WHO-a i mjerenja djeteta`,
            sexMissing: 'Odaberite spol djeteta za WHO krivulje i percentile.',
            measureNoValue: 'Unesite barem jednu vrijednost.',
            measureRange: (label, min, max, unitName) => `${label}: unesite vrijednost od ${min} do ${max} ${unitName}.`,
            measureDate: 'Datum mjerenja mora biti između rođenja i današnjeg dana.',
            beforeTerm: 'prije termina',
            after24: 'nakon 24 mj.',
            removeMeasurement: (date) => `Ukloni mjerenje od ${date}`,
            correctedNote: 'Prikazano prema korigiranoj dobi (od termina poroda).',
            axisMonths: 'mjeseci',
        },
        en: {
            word: (n, key) => (n === 1 ? key : `${key}s`),
            and: 'and',
            today: 'today',
            tomorrow: 'tomorrow',
            inDays: (n) => `in ${unit(n, 'day', 'en')}`,
            ago: (n) => `${unit(n, 'day', 'en')} ago`,
            birthday: (y) => `${ordinalEn(y)} birthday`,
            pregnancyMilestone: {
                second: 'Second trimester', half: 'Halfway', third: 'Third trimester',
                term: 'Full term', due: 'Due date',
            },
            date: (d) => `${d.getUTCDate()} ${MONTH_NAMES_EN[d.getUTCMonth()]} ${d.getUTCFullYear()}`,
            at: 'at',
            child: (n) => `Child ${n}`,
            childAgeHeading: 'Child’s age',
            born: 'Born',
            age: 'Age',
            or: 'or',
            pregnancy: 'Pregnancy',
            dueDate: 'Due date',
            pregnancyDetail: (s) => `${s.weeks}+${s.weekDays} · week\u00a0${s.week} · ${['first', 'second', 'third'][s.trimester - 1]}\u00a0trimester`,
            week: (n) => `week ${n}`,
            progress: (percent) => `${percent}% of pregnancy`,
            dateLabel: {
                lmp: 'First day of last period', due: 'Due date',
                ivf: 'Embryo transfer date', ultrasound: 'Ultrasound date',
            },
            errors: {
                birthMissing: 'Enter the date of birth.',
                birthInvalid: 'Invalid date or time of birth.',
                birthFuture: 'The date of birth can’t be in the future. For a pregnancy, choose “Pregnancy”.',
                dateMissing: 'Enter a date.',
                dateInvalid: 'Invalid date.',
                lmpFuture: 'The first day of the last period can’t be in the future.',
                dueInvalid: 'Invalid due date.',
                dueTooLate: 'The due date can be at most 20 weeks after the birth.',
                dateFuture: 'The date can’t be in the future.',
                pregnancyTooOld: 'With these details the pregnancy would be over 42 weeks. If the baby is born, choose “Baby”.',
                gestationInvalid: 'Enter the weeks (0–42) and days (0–6) from the ultrasound.',
                dueTooFar: 'The due date is too far in the future (more than 40 weeks).',
                lmpTooOld: 'The last period was more than 42 weeks ago. If the baby is born, choose “Baby”.',
                duePassed: 'The due date was more than two weeks ago. If the baby is born, choose “Baby”.',
            },
            linkCopied: 'Link copied.',
            textCopied: 'Text copied.',
            pictureSaved: 'Picture saved.',
            pictureFailed: 'Couldn’t create the picture.',
            copyFailed: 'Copying failed.',
            childRemoved: (label) => `Removed: “${label}”.`,
            measurementRemoved: (date) => `Removed: the measurement of ${date}.`,
            undo: 'Undo',
            lastBackup: (date) => `Last backup: ${date}`,
            lastBackupNever: 'Last backup: none yet',
            corrected: 'Corrected age',
            correctedNotNeeded: 'Not needed',
            correctedStarts: 'Starts at the due date',
            correctedStartsIn: (when, due) => `${when} (due ${due})`,
            gestationAtBirth: (w, d) => `Born at ${w}+${d}\u00a0weeks`,
            correctedUntil2: 'Correction is usually used until age 2.',
            backupRestored: 'Data restored.',
            backupNothingNew: 'Nothing new – everything was already saved.',
            backupInvalid: 'This isn’t a valid backup.',
            backupTooLarge: 'The file is too large for a backup.',
            backupLinkCopied: 'Transfer link copied.',
            backupReplacePregnancy: 'The backup has different pregnancy data. Replace the current data?',
            measures: { weight: 'Weight', length: 'Length', head: 'Head circumference' },
            growthChartLabel: (label) => `Growth chart: ${label}, WHO percentiles and the child's measurements`,
            sexMissing: 'Choose the child’s sex for the WHO charts and percentiles.',
            measureNoValue: 'Enter at least one value.',
            measureRange: (label, min, max, unitName) => `${label}: enter a value from ${min} to ${max} ${unitName}.`,
            measureDate: 'The date must be between the birth and today.',
            beforeTerm: 'before the due date',
            after24: 'after 24 months',
            removeMeasurement: (date) => `Remove the measurement of ${date}`,
            correctedNote: 'Shown by corrected age (from the due date).',
            axisMonths: 'months',
        },
        de: {
            word: (n, key) => WORDS_DE[key][n === 1 ? 0 : 1],
            and: 'und',
            today: 'heute',
            tomorrow: 'morgen',
            // After "in" and "vor" German uses the dative plural: "in 5 Tagen"
            inDays: (n) => (n === 1 ? 'in 1 Tag' : `in ${n} Tagen`),
            ago: (n) => (n === 1 ? 'vor 1 Tag' : `vor ${n} Tagen`),
            birthday: (y) => `${y}. Geburtstag`,
            pregnancyMilestone: {
                second: '2. Trimester', half: 'Halbzeit', third: '3. Trimester',
                term: 'Termingerecht', due: 'Geburtstermin',
            },
            date: (d) => `${d.getUTCDate()}. ${MONTH_NAMES_DE[d.getUTCMonth()]} ${d.getUTCFullYear()}`,
            at: 'um',
            child: (n) => `Kind ${n}`,
            childAgeHeading: 'Alter des Kindes',
            born: 'Geburt',
            age: 'Alter',
            or: 'bzw.',
            pregnancy: 'Schwangerschaft',
            dueDate: 'Geburtstermin',
            pregnancyDetail: (s) => `${s.weeks}+${s.weekDays} · ${s.week}.\u00a0SSW · ${s.trimester}.\u00a0Trimester`,
            week: (n) => `${n}. SSW`,
            progress: (percent) => `${percent} % der Schwangerschaft`,
            dateLabel: {
                lmp: 'Erster Tag der letzten Periode', due: 'Geburtstermin',
                ivf: 'Datum des Embryotransfers', ultrasound: 'Datum des Ultraschalls',
            },
            errors: {
                birthMissing: 'Bitte das Geburtsdatum eingeben.',
                birthInvalid: 'Ungültiges Geburtsdatum oder ungültige Geburtszeit.',
                birthFuture: 'Das Geburtsdatum kann nicht in der Zukunft liegen. Für eine Schwangerschaft „Schwangerschaft“ wählen.',
                dateMissing: 'Bitte ein Datum eingeben.',
                dateInvalid: 'Ungültiges Datum.',
                lmpFuture: 'Der erste Tag der letzten Periode kann nicht in der Zukunft liegen.',
                dueInvalid: 'Ungültiger Geburtstermin.',
                dueTooLate: 'Der Geburtstermin darf höchstens 20 Wochen nach der Geburt liegen.',
                dateFuture: 'Das Datum kann nicht in der Zukunft liegen.',
                pregnancyTooOld: 'Mit diesen Angaben wäre die Schwangerschaft länger als 42 Wochen. Wenn das Baby geboren ist, „Baby“ wählen.',
                gestationInvalid: 'Bitte die Wochen (0–42) und Tage (0–6) aus dem Ultraschall eingeben.',
                dueTooFar: 'Der Geburtstermin liegt zu weit in der Zukunft (mehr als 40 Wochen).',
                lmpTooOld: 'Die letzte Periode liegt mehr als 42 Wochen zurück. Wenn das Baby geboren ist, „Baby“ wählen.',
                duePassed: 'Der Geburtstermin liegt mehr als zwei Wochen zurück. Wenn das Baby geboren ist, „Baby“ wählen.',
            },
            linkCopied: 'Link kopiert.',
            textCopied: 'Text kopiert.',
            pictureSaved: 'Bild gespeichert.',
            pictureFailed: 'Das Bild konnte nicht erstellt werden.',
            copyFailed: 'Kopieren fehlgeschlagen.',
            childRemoved: (label) => `Entfernt: „${label}“.`,
            measurementRemoved: (date) => `Entfernt: Messung vom ${date}.`,
            undo: 'Rückgängig',
            lastBackup: (date) => `Letzte Sicherung: ${date}`,
            lastBackupNever: 'Letzte Sicherung: noch keine',
            corrected: 'Korrigiertes Alter',
            correctedNotNeeded: 'Nicht nötig',
            correctedStarts: 'Beginnt am Geburtstermin',
            correctedStartsIn: (when, due) => `${when} (Termin ${due})`,
            gestationAtBirth: (w, d) => `Geboren in SSW\u00a0${w}+${d}`,
            correctedUntil2: 'Die Korrektur wird meist bis zum 2. Geburtstag verwendet.',
            backupRestored: 'Daten wiederhergestellt.',
            backupNothingNew: 'Nichts Neues – alles war schon gespeichert.',
            backupInvalid: 'Das ist keine gültige Sicherung.',
            backupTooLarge: 'Die Datei ist zu groß für eine Sicherung.',
            backupLinkCopied: 'Übertragungslink kopiert.',
            backupReplacePregnancy: 'Die Sicherung enthält andere Schwangerschaftsdaten. Die aktuellen ersetzen?',
            measures: { weight: 'Gewicht', length: 'Länge', head: 'Kopfumfang' },
            growthChartLabel: (label) => `Wachstumskurve: ${label}, WHO-Perzentilen und die Messungen des Kindes`,
            sexMissing: 'Für die WHO-Kurven und Perzentilen das Geschlecht des Kindes wählen.',
            measureNoValue: 'Bitte mindestens einen Wert eingeben.',
            measureRange: (label, min, max, unitName) => `${label}: bitte einen Wert von ${min} bis ${max} ${unitName} eingeben.`,
            measureDate: 'Das Datum muss zwischen der Geburt und heute liegen.',
            beforeTerm: 'vor dem Termin',
            after24: 'nach 24 Monaten',
            removeMeasurement: (date) => `Messung vom ${date} entfernen`,
            correctedNote: 'Nach korrigiertem Alter (ab dem Geburtstermin).',
            axisMonths: 'Monate',
        },
        it: {
            word: (n, key) => WORDS_IT[key][n === 1 ? 0 : 1],
            and: 'e',
            today: 'oggi',
            tomorrow: 'domani',
            inDays: (n) => `tra ${unit(n, 'day', 'it')}`,
            ago: (n) => `${unit(n, 'day', 'it')} fa`,
            birthday: (y) => `${y}° compleanno`,
            pregnancyMilestone: {
                second: '2° trimestre', half: 'Metà gravidanza', third: '3° trimestre',
                term: 'A termine', due: 'Data presunta del parto',
            },
            date: (d) => `${d.getUTCDate()} ${MONTH_NAMES_IT[d.getUTCMonth()]} ${d.getUTCFullYear()}`,
            at: 'alle',
            child: (n) => `Bambino ${n}`,
            childAgeHeading: 'Età del bambino',
            born: 'Nascita',
            age: 'Età',
            or: 'ovvero',
            pregnancy: 'Gravidanza',
            dueDate: 'Data presunta del parto',
            pregnancyDetail: (s) => `${s.weeks}+${s.weekDays} · ${s.week}ª\u00a0settimana · ${s.trimester}°\u00a0trimestre`,
            week: (n) => `${n}ª settimana`,
            progress: (percent) => `${percent}% della gravidanza`,
            dateLabel: {
                lmp: 'Primo giorno dell’ultima mestruazione', due: 'Data presunta del parto',
                ivf: 'Data del transfer embrionale', ultrasound: 'Data dell’ecografia',
            },
            errors: {
                birthMissing: 'Inserisci la data di nascita.',
                birthInvalid: 'Data o ora di nascita non valida.',
                birthFuture: 'La data di nascita non può essere nel futuro. Per una gravidanza scegli «Gravidanza».',
                dateMissing: 'Inserisci una data.',
                dateInvalid: 'Data non valida.',
                lmpFuture: 'Il primo giorno dell’ultima mestruazione non può essere nel futuro.',
                dueInvalid: 'Data presunta del parto non valida.',
                dueTooLate: 'La data presunta del parto può essere al massimo 20 settimane dopo la nascita.',
                dateFuture: 'La data non può essere nel futuro.',
                pregnancyTooOld: 'Con questi dati la gravidanza supererebbe le 42 settimane. Se il bambino è nato, scegli «Bambino».',
                gestationInvalid: 'Inserisci le settimane (0–42) e i giorni (0–6) dell’ecografia.',
                dueTooFar: 'La data presunta del parto è troppo lontana (oltre 40 settimane).',
                lmpTooOld: 'L’ultima mestruazione risale a più di 42 settimane fa. Se il bambino è nato, scegli «Bambino».',
                duePassed: 'La data presunta del parto è passata da più di due settimane. Se il bambino è nato, scegli «Bambino».',
            },
            linkCopied: 'Link copiato.',
            textCopied: 'Testo copiato.',
            pictureSaved: 'Immagine salvata.',
            pictureFailed: 'Impossibile creare l’immagine.',
            copyFailed: 'Copia non riuscita.',
            childRemoved: (label) => `Eliminato: «${label}».`,
            measurementRemoved: (date) => `Eliminata: misurazione del ${date}.`,
            undo: 'Annulla',
            lastBackup: (date) => `Ultimo backup: ${date}`,
            lastBackupNever: 'Ultimo backup: ancora nessuno',
            corrected: 'Età corretta',
            correctedNotNeeded: 'Non necessaria',
            correctedStarts: 'Inizia dalla data presunta del parto',
            correctedStartsIn: (when, due) => `${when} (termine ${due})`,
            gestationAtBirth: (w, d) => `Età gestazionale alla nascita:\u00a0${w}+${d}`,
            correctedUntil2: 'Di solito l’età corretta si usa fino ai 2 anni.',
            backupRestored: 'Dati ripristinati.',
            backupNothingNew: 'Niente di nuovo – era già tutto salvato.',
            backupInvalid: 'Questo non è un backup valido.',
            backupTooLarge: 'Il file è troppo grande per un backup.',
            backupLinkCopied: 'Link di trasferimento copiato.',
            backupReplacePregnancy: 'Il backup contiene altri dati sulla gravidanza. Sostituire quelli attuali?',
            measures: { weight: 'Peso', length: 'Lunghezza', head: 'Circonferenza cranica' },
            growthChartLabel: (label) => `Curva di crescita: ${label}, percentili OMS e misurazioni del bambino`,
            sexMissing: 'Scegli il sesso del bambino per le curve e i percentili OMS.',
            measureNoValue: 'Inserisci almeno un valore.',
            measureRange: (label, min, max, unitName) => `${label}: inserisci un valore da ${min} a ${max} ${unitName}.`,
            measureDate: 'La data deve essere tra la nascita e oggi.',
            beforeTerm: 'prima del termine',
            after24: 'dopo i 24 mesi',
            removeMeasurement: (date) => `Rimuovi la misurazione del ${date}`,
            correctedNote: 'In base all’età corretta (dalla data presunta del parto).',
            axisMonths: 'mesi',
        },
    };

    // Unknown values (including the extra arguments Array.map passes) fall back to Croatian
    function texts(lang) {
        return typeof lang === 'string' && Object.prototype.hasOwnProperty.call(TEXT, lang) ? TEXT[lang] : TEXT.hr;
    }

    function unit(n, key, lang = 'hr') {
        return `${n} ${texts(lang).word(n, key)}`;
    }

    // "a", "a i b", "a, b i c" ("a, b and c"); zero parts are left out unless all are zero
    function joinParts(parts, lang = 'hr') {
        const shown = parts.filter(([n]) => n > 0);
        const list = (shown.length ? shown : parts.slice(-1)).map(([n, key]) => unit(n, key, lang));
        if (list.length === 1) return list[0];
        return `${list.slice(0, -1).join(', ')} ${texts(lang).and} ${list[list.length - 1]}`;
    }

    // Like a clock: every part shown, numbers at least two digits ("592 dana, 03 sata, 00 minuta i 07 sekundi");
    // the word still follows the real number
    function joinClock(parts, lang = 'hr') {
        const list = parts.map(([n, key]) => `${pad(n)} ${texts(lang).word(n, key)}`);
        return `${list.slice(0, -1).join(', ')} ${texts(lang).and} ${list[list.length - 1]}`;
    }

    Object.assign(BC, {
        FORMS, plural, MONTH_NAMES_EN, pad, ordinalEn, TEXT, texts, unit, joinParts, joinClock,
    });
})(globalThis.BC = globalThis.BC || {});
