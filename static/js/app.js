(function () {
    'use strict';

    const STORAGE_KEY = 'birth'; // v2.0–2.5: a single child; moved into CHILDREN_KEY on first load
    const CHILDREN_KEY = 'children';
    const ACTIVE_CHILD_KEY = 'activeChild';
    const NAME_MAX = 40;
    const MODE_KEY = 'mode';
    const PREGNANCY_KEY = 'pregnancy';
    const LEGACY_COOKIE = 'datetime';
    const DAY = 24 * 60 * 60 * 1000;
    const DAY_MILESTONES = [100, 200, 300, 500, 1000, 2000, 3000, 5000, 10000];
    const PREGNANCY_DAYS = 280; // due date = first day of the last period + 280 days (Naegele's rule)
    const PREGNANCY_MILESTONES = [[14, 'second'], [20, 'half'], [28, 'third'], [37, 'term'], [40, 'due']];

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
            inDays: (days) => `za ${days}`,
            ago: (days) => `prije ${days}`,
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
            dateLabel: { lmp: 'Prvi dan zadnje menstruacije', due: 'Termin poroda' },
            errors: {
                birthMissing: 'Unesite datum rođenja.',
                birthInvalid: 'Neispravan datum ili vrijeme rođenja.',
                birthFuture: 'Datum rođenja ne može biti u budućnosti. Za trudnoću odaberite „Trudnoća”.',
                dateMissing: 'Unesite datum.',
                dateInvalid: 'Neispravan datum.',
                lmpFuture: 'Datum zadnje menstruacije ne može biti u budućnosti.',
                dueInvalid: 'Neispravan termin poroda.',
                dueTooLate: 'Termin poroda može biti najviše 20 tjedana nakon rođenja.',
                dueTooFar: 'Termin je predaleko u budućnosti (više od 40 tjedana).',
                lmpTooOld: 'Zadnja menstruacija je prije više od 42 tjedna. Ako je beba rođena, odaberite „Beba je rođena”.',
                duePassed: 'Termin je prošao prije više od dva tjedna. Ako je beba rođena, odaberite „Beba je rođena”.',
            },
            linkCopied: 'Poveznica je kopirana.',
            textCopied: 'Tekst je kopiran.',
            copyFailed: 'Kopiranje nije uspjelo.',
            confirmRemove: (label) => `Ukloniti „${label}” s popisa?`,
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
        },
        en: {
            word: (n, key) => (n === 1 ? key : `${key}s`),
            and: 'and',
            today: 'today',
            tomorrow: 'tomorrow',
            inDays: (days) => `in ${days}`,
            ago: (days) => `${days} ago`,
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
            dateLabel: { lmp: 'First day of last period', due: 'Due date' },
            errors: {
                birthMissing: 'Enter the date of birth.',
                birthInvalid: 'Invalid date or time of birth.',
                birthFuture: 'The date of birth can’t be in the future. For a pregnancy, choose “Pregnancy”.',
                dateMissing: 'Enter a date.',
                dateInvalid: 'Invalid date.',
                lmpFuture: 'The first day of the last period can’t be in the future.',
                dueInvalid: 'Invalid due date.',
                dueTooLate: 'The due date can be at most 20 weeks after the birth.',
                dueTooFar: 'The due date is too far in the future (more than 40 weeks).',
                lmpTooOld: 'The last period was more than 42 weeks ago. If the baby is born, choose “Baby is born”.',
                duePassed: 'The due date was more than two weeks ago. If the baby is born, choose “Baby is born”.',
            },
            linkCopied: 'Link copied.',
            textCopied: 'Text copied.',
            copyFailed: 'Copying failed.',
            confirmRemove: (label) => `Remove “${label}” from the list?`,
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
        },
    };

    // Unknown values (including the extra arguments Array.map passes) fall back to Croatian
    function texts(lang) {
        return lang === 'en' ? TEXT.en : TEXT.hr;
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

    // All math is done on wall-clock time stored as UTC milliseconds, so DST
    // changes don't shift the result.
    function wallClockNow() {
        const d = new Date();
        return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate(),
            d.getHours(), d.getMinutes(), d.getSeconds());
    }

    function parseBirth(date, time) {
        const dm = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date || '');
        const tm = /^(\d{2}):(\d{2})/.exec(time || '00:00');
        if (!dm || !tm) return null;
        const [y, mo, d] = dm.slice(1).map(Number);
        const [h, mi] = tm.slice(1).map(Number);
        const ms = Date.UTC(y, mo - 1, d, h, mi);
        const check = new Date(ms);
        if (check.getUTCMonth() !== mo - 1 || check.getUTCDate() !== d || h > 23 || mi > 59) return null;
        return ms;
    }

    // Same day clipping as dateutil's relativedelta: 31 Jan + 1 month = 28/29 Feb
    function addMonths(ms, months) {
        const d = new Date(ms);
        const target = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + months, 1,
            d.getUTCHours(), d.getUTCMinutes(), d.getUTCSeconds()));
        const lastDay = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
        target.setUTCDate(Math.min(d.getUTCDate(), lastDay));
        return target.getTime();
    }

    // The real moment of a wall-clock time, in the visitor's time zone
    function wallToReal(ms) {
        const d = new Date(ms);
        return new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(),
            d.getUTCHours(), d.getUTCMinutes(), d.getUTCSeconds()).getTime();
    }

    // birth and now are wall-clock times, right for calendar values (years, months, days, weeks).
    // elapsed is the real time in between; it differs by an hour when a summer/winter time change
    // lies in between, so the elapsed days, hours, minutes and seconds use it.
    function calculateAge(birth, now, elapsed = now - birth) {
        const b = new Date(birth);
        const n = new Date(now);
        let months = (n.getUTCFullYear() - b.getUTCFullYear()) * 12 + n.getUTCMonth() - b.getUTCMonth();
        if (addMonths(birth, months) > now) months--;

        const totalDays = Math.floor((now - birth) / DAY);
        const real = Math.max(elapsed, 0);
        return {
            years: Math.floor(months / 12),
            months: months % 12,
            days: Math.floor((now - addMonths(birth, months)) / DAY),
            weeks: Math.floor(totalDays / 7),
            weekDays: totalDays % 7,
            totalDays,
            elapsedDays: Math.floor(real / DAY),
            hours: Math.floor(real / 3600000) % 24,
            minutes: Math.floor(real / 60000) % 60,
            seconds: Math.floor(real / 1000) % 60,
        };
    }

    const MAX_DAYS_EARLY = 20 * 7; // born at 20+0 weeks or later

    // Corrected age for a baby born before the due date: the age counted from the due date.
    // Dates only for the due date; birth and now are wall-clock times.
    function correctedAge(birth, due, now) {
        const birthDay = startOfDay(birth);
        const dueDay = startOfDay(due);
        const daysEarly = Math.round((dueDay - birthDay) / DAY);
        const gestation = PREGNANCY_DAYS - daysEarly;
        const result = {
            premature: daysEarly > 0,
            daysEarly,
            gestationWeeks: Math.floor(gestation / 7),
            gestationDays: gestation % 7,
            started: now >= dueDay,
            daysUntilDue: Math.max(0, Math.round((dueDay - startOfDay(now)) / DAY)),
        };
        if (result.premature && result.started) result.age = calculateAge(dueDay, now);
        return result;
    }

    function correctedAgeError(birth, due, lang = 'hr') {
        const daysEarly = Math.round((startOfDay(due) - startOfDay(birth)) / DAY);
        return daysEarly > MAX_DAYS_EARLY ? texts(lang).errors.dueTooLate : null;
    }

    function startOfDay(ms) {
        const d = new Date(ms);
        return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
    }

    // Upcoming month birthdays (1–23 months), birthdays and day counts, nearest first.
    // Dates only: a milestone is "today" for the whole day.
    // Every milestone from today on, nearest first; key identifies it (d100, m6, y1)
    function babyMilestones(birth, now, lang = 'hr') {
        const birthDay = startOfDay(birth);
        const today = startOfDay(now);
        const all = DAY_MILESTONES.map((n) => ({ key: `d${n}`, date: birthDay + n * DAY, label: unit(n, 'day', lang) }));
        for (let m = 1; m < 24; m++) {
            if (m % 12) all.push({ key: `m${m}`, date: addMonths(birthDay, m), label: unit(m, 'month', lang) });
        }
        for (let y = 1; y <= 120; y++) {
            all.push({ key: `y${y}`, date: addMonths(birthDay, y * 12), label: texts(lang).birthday(y) });
        }
        return all
            .filter((m) => m.date >= today)
            .sort((a, b) => a.date - b.date)
            .map((m) => ({ ...m, daysLeft: Math.round((m.date - today) / DAY) }));
    }

    function upcomingMilestones(birth, now, count = 3, lang = 'hr') {
        return babyMilestones(birth, now, lang).slice(0, count).map(({ key, ...m }) => m);
    }

    function countdown(daysLeft, lang = 'hr') {
        const t = texts(lang);
        if (daysLeft === 0) return t.today;
        if (daysLeft === 1) return t.tomorrow;
        return t.inDays(unit(daysLeft, 'day', lang));
    }

    function formatDate(ms, lang = 'hr') {
        return texts(lang).date(new Date(ms));
    }

    function formatBirth(ms, hasTime, lang = 'hr') {
        const d = new Date(ms);
        const date = formatDate(ms, lang);
        return hasTime ? `${date} ${texts(lang).at} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}` : date;
    }

    function todayValue() {
        const d = new Date();
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }

    function isoDate(ms) {
        return new Date(ms).toISOString().slice(0, 10);
    }

    // basis: 'due' (due date) or 'lmp' (first day of the last period); returns the LMP date in ms
    function lmpFrom(basis, dateMs) {
        return basis === 'lmp' ? dateMs : dateMs - PREGNANCY_DAYS * DAY;
    }

    function pregnancyStatus(lmp, now) {
        const today = startOfDay(now);
        const days = Math.round((today - lmp) / DAY);
        const due = lmp + PREGNANCY_DAYS * DAY;
        return {
            weeks: Math.floor(days / 7),
            weekDays: days % 7,
            totalDays: days,
            week: Math.floor(days / 7) + 1,                  // "35. tjedan" at 34+2
            trimester: days < 14 * 7 ? 1 : days < 28 * 7 ? 2 : 3,
            due,
            daysToDue: Math.round((due - today) / DAY),
            progress: Math.min(days, PREGNANCY_DAYS),
        };
    }

    // Error message, or null when the date makes sense for an ongoing pregnancy (up to 42 weeks)
    function pregnancyError(basis, lmp, now, lang = 'hr') {
        const errors = texts(lang).errors;
        const days = Math.round((startOfDay(now) - lmp) / DAY);
        if (days < 0) {
            return basis === 'lmp' ? errors.lmpFuture : errors.dueTooFar;
        }
        if (days > 42 * 7) {
            return basis === 'lmp' ? errors.lmpTooOld : errors.duePassed;
        }
        return null;
    }

    function pregnancyMilestones(lmp, now, count = 3, lang = 'hr') {
        const today = startOfDay(now);
        return PREGNANCY_MILESTONES
            .map(([weeks, key]) => ({ key, date: lmp + weeks * 7 * DAY, label: texts(lang).pregnancyMilestone[key] }))
            .filter((m) => m.date >= today)
            .slice(0, count)
            .map((m) => ({ ...m, daysLeft: Math.round((m.date - today) / DAY) }));
    }

    // --- Calendar export (iCalendar, RFC 5545) ---

    const CALENDAR_HORIZON_DAYS = 2 * 365; // baby milestones in the next two years

    function icsDate(ms) {
        return isoDate(ms).replace(/-/g, '');
    }

    function icsEscape(text) {
        return String(text).replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r?\n/g, '\\n');
    }

    // Lines longer than 75 octets (UTF-8 bytes, not characters) continue on the next line after a space
    function icsFold(line) {
        const parts = [];
        let current = '';
        let octets = 0;
        for (const ch of line) {
            const code = ch.codePointAt(0);
            const size = code < 0x80 ? 1 : code < 0x800 ? 2 : code < 0x10000 ? 3 : 4;
            const limit = parts.length ? 74 : 75; // continuation lines start with a space
            if (octets + size > limit) {
                parts.push(current);
                current = '';
                octets = 0;
            }
            current += ch;
            octets += size;
        }
        parts.push(current);
        return parts.join('\r\n ');
    }

    // events: [{ uid, date (ms), summary, description }]; stamp: the export time in ms
    function buildIcs(events, stamp) {
        const dtstamp = new Date(stamp).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
        const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Baby Calculator//bc.luka-pejakovic.from.hr//HR',
            'CALSCALE:GREGORIAN', 'METHOD:PUBLISH'];
        events.forEach((e) => {
            lines.push('BEGIN:VEVENT', `UID:${e.uid}`, `DTSTAMP:${dtstamp}`,
                `DTSTART;VALUE=DATE:${icsDate(e.date)}`, `DTEND;VALUE=DATE:${icsDate(e.date + DAY)}`,
                `SUMMARY:${icsEscape(e.summary)}`, `DESCRIPTION:${icsEscape(e.description)}`, 'TRANSP:TRANSPARENT',
                // Reminder at 9:00 on the day
                'BEGIN:VALARM', 'ACTION:DISPLAY', `DESCRIPTION:${icsEscape(e.summary)}`, 'TRIGGER;RELATED=START:PT9H',
                'END:VALARM', 'END:VEVENT');
        });
        lines.push('END:VCALENDAR');
        return `${lines.map(icsFold).join('\r\n')}\r\n`;
    }

    // Stable ids, so importing again updates the events instead of adding copies
    function babyCalendarEvents(birth, label, now, lang = 'hr', site = '') {
        const limit = startOfDay(now) + CALENDAR_HORIZON_DAYS * DAY;
        return babyMilestones(birth, now, lang)
            .filter((m) => m.date <= limit)
            .map((m) => ({
                uid: `${isoDate(birth)}-${m.key}@bc.luka-pejakovic.from.hr`,
                date: m.date,
                summary: `${label}: ${m.label}`,
                description: `Baby Calculator · ${site}`,
            }));
    }

    function pregnancyCalendarEvents(lmp, now, lang = 'hr', site = '') {
        return pregnancyMilestones(lmp, now, PREGNANCY_MILESTONES.length, lang).map((m) => ({
            uid: `pregnancy-${isoDate(lmp)}-${m.key}@bc.luka-pejakovic.from.hr`,
            date: m.date,
            summary: `${texts(lang).pregnancy}: ${m.label}`,
            description: `Baby Calculator · ${site}`,
        }));
    }

    function dueCountdown(daysToDue, lang = 'hr') {
        if (daysToDue < 0) return texts(lang).ago(unit(-daysToDue, 'day', lang));
        return countdown(daysToDue, lang);
    }

    // #t=YYYY-MM-DD (due date); older links used ?t=
    function readSharedPregnancy(search) {
        const match = /[?&#]t=([^&#]*)/.exec(search || '');
        if (!match) return null;
        const date = decodeURIComponent(match[1]);
        return parseBirth(date, '') === null ? null : { basis: 'due', date };
    }

    // #d=YYYY-MM-DD or #d=YYYY-MM-DDTHH:MM, optionally &n=<name>&due=YYYY-MM-DD (older links used ?d=)
    function readSharedBirth(search) {
        const match = /[?&#]d=([^&#]*)/.exec(search || '');
        if (!match) return null;
        const [date, time = ''] = decodeURIComponent(match[1]).split('T');
        if (parseBirth(date, time) === null) return null;
        const nameMatch = /[?&#]n=([^&#]*)/.exec(search);
        let name = '';
        try {
            name = nameMatch ? decodeURIComponent(nameMatch[1].replace(/\+/g, ' ')).trim().slice(0, NAME_MAX) : '';
        } catch (e) { /* malformed escape: ignore the name */ }
        const dueMatch = /[?&#]due=([^&#]*)/.exec(search);
        const due = dueMatch && parseBirth(dueMatch[1], '') !== null ? dueMatch[1] : '';
        return { date, time, name, due };
    }

    // The data goes after "#", which browsers never send to the server (older links used "?d=")
    function buildShareUrl(base, date, time, name = '', due = '') {
        const n = name ? `&n=${encodeURIComponent(name)}` : '';
        return `${base}#d=${date}${time ? `T${time}` : ''}${n}${due ? `&due=${due}` : ''}`;
    }

    // --- Several children: [{ id, name, date, time }] ---

    function cleanChild(child) {
        return {
            id: child.id,
            name: String(child.name || '').trim().slice(0, NAME_MAX),
            date: child.date,
            time: child.time || '',
            // Due date for the corrected age of a premature baby; '' when not given
            due: typeof child.due === 'string' && parseBirth(child.due, '') !== null ? child.due : '',
        };
    }

    // Valid children from storage; a v2.x single saved birth becomes the first child
    function normalizeChildren(stored, legacyBirth) {
        const valid = (c) => c && typeof c.date === 'string' && parseBirth(c.date, c.time || '') !== null;
        let list = Array.isArray(stored) ? stored.filter(valid) : [];
        if (!list.length && valid(legacyBirth)) list = [{ name: '', ...legacyBirth }];
        // Ids must be unique positive integers; renumber if storage was edited by hand
        const ids = list.map((c) => c.id);
        const ok = ids.every((id) => Number.isInteger(id) && id > 0) && new Set(ids).size === ids.length;
        return list.map((c, i) => cleanChild({ ...c, id: ok ? c.id : i + 1 }));
    }

    function nextChildId(children) {
        return children.reduce((max, c) => Math.max(max, c.id), 0) + 1;
    }

    function childLabel(child, index, lang = 'hr') {
        return child.name || texts(lang).child(index + 1);
    }

    // A shared child selects an existing child with the same birth, otherwise it is added
    function addSharedChild(children, shared) {
        const same = children.find((c) => c.date === shared.date && c.time === (shared.time || ''));
        if (same) {
            const updated = children.map((c) => (c === same ? {
                ...c,
                name: c.name || shared.name || '',
                due: c.due || shared.due || '',
            } : c));
            return { children: updated.map(cleanChild), activeId: same.id };
        }
        const child = cleanChild({ ...shared, id: nextChildId(children) }); // ignore any id it brings
        return { children: [...children, child], activeId: child.id };
    }

    // --- Backup and restore ---

    const BACKUP_APP = 'baby-calculator';
    const BACKUP_VERSION = 1;
    const BACKUP_MAX_BYTES = 100 * 1024;

    function validPregnancy(p) {
        return p && (p.basis === 'due' || p.basis === 'lmp') && parseBirth(p.date, '') !== null
            ? { basis: p.basis, date: p.date } : null;
    }

    function makeBackup(state, exportedAt) {
        return {
            app: BACKUP_APP,
            version: BACKUP_VERSION,
            exportedAt,
            children: state.children.map(cleanChild),
            activeChild: state.activeChild,
            pregnancy: validPregnancy(state.pregnancy),
            mode: state.mode === 'pregnancy' ? 'pregnancy' : 'baby',
        };
    }

    // A backup object from JSON text, cleaned like stored data; null if it isn't one
    function parseBackup(text) {
        let data;
        try {
            data = JSON.parse(text);
        } catch (e) {
            return null;
        }
        if (!data || data.app !== BACKUP_APP || data.version !== BACKUP_VERSION) return null;
        return {
            children: normalizeChildren(data.children, null),
            pregnancy: validPregnancy(data.pregnancy),
            mode: data.mode === 'pregnancy' ? 'pregnancy' : 'baby',
        };
    }

    // Imported children are added next to the existing ones; a child with the same birth is
    // not duplicated but gets a missing name or due date
    function mergeChildren(local, imported) {
        let children = local;
        let added = 0;
        let changed = 0;
        imported.forEach((child) => {
            const before = JSON.stringify(children);
            const count = children.length;
            ({ children } = addSharedChild(children, child));
            if (children.length > count) added += 1;
            else if (JSON.stringify(children) !== before) changed += 1;
        });
        return { children, added, changed };
    }

    // The data travels after "#", which browsers never send to the server
    function buildBackupLink(base, backup) {
        return `${base}#backup=${encodeURIComponent(JSON.stringify(backup))}`;
    }

    function readBackupLink(hash) {
        const match = /^#backup=(.+)$/.exec(hash || '');
        if (!match) return null;
        try {
            return parseBackup(decodeURIComponent(match[1]));
        } catch (e) {
            return null;
        }
    }

    function removeChild(children, id) {
        const index = children.findIndex((c) => c.id === id);
        const rest = children.filter((c) => c.id !== id);
        const next = rest[Math.min(Math.max(index, 0), rest.length - 1)];
        return { children: rest, activeId: next ? next.id : null };
    }

    // Children from storage; migrates the v2.x single 'birth' entry and the v1.x cookie
    function loadChildren() {
        let legacy = restore(STORAGE_KEY);
        const match = document.cookie.match(new RegExp(`(?:^|; )${LEGACY_COOKIE}=([^;]*)`));
        if (match) {
            document.cookie = `${LEGACY_COOKIE}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
            const [date, time] = decodeURIComponent(match[1]).split('T');
            legacy = legacy || { date, time: time || '' };
        }
        const children = normalizeChildren(restore(CHILDREN_KEY), legacy);
        store(CHILDREN_KEY, children);
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch (e) { /* storage unavailable */ }
        return children;
    }

    function store(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (e) { /* storage unavailable */ }
    }

    function restore(key) {
        try {
            return JSON.parse(localStorage.getItem(key) || 'null');
        } catch (e) {
            return null;
        }
    }

    if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', function () {
        const $ = (id) => document.getElementById(id);
        // The /en/ page has <html lang="en">
        const lang = document.documentElement.lang === 'en' ? 'en' : 'hr';
        const t = texts(lang);

        // The chosen language is kept in a cookie; the server redirects "/" to "/en/" when it says "en".
        // Offline (page from the service worker cache) the page does the redirect itself.
        const savedLang = (document.cookie.match(/(?:^|; )lang=(hr|en)(?:;|$)/) || [])[1];
        if (lang === 'hr' && savedLang === 'en') {
            location.replace(`/en/${location.search}${location.hash}`);
            return;
        }
        document.querySelectorAll('.lang-switch a').forEach((link) => link.addEventListener('click', function () {
            const secure = location.protocol === 'https:' ? '; Secure' : '';
            document.cookie = `lang=${link.hreflang}; path=/; max-age=${365 * 24 * 3600}; SameSite=Lax${secure}`;
        }));
        const modeInputs = document.querySelectorAll('input[name="mode"]');
        const basisInputs = document.querySelectorAll('input[name="basis"]');
        const form = $('birth-form');
        const dateInput = $('birth-date');
        const timeInput = $('birth-time');
        const nameInput = $('child-name');
        const childrenBox = $('children');
        const childList = $('child-list');
        const addChildButton = $('add-child');
        const removeChildButton = $('remove-child');
        const resultTitle = $('result-title');
        const dueInput = $('due-date');
        const premature = $('premature');
        const corrected = {
            card: $('corrected-card'),
            value: $('corrected-value'),
            detail: $('corrected-detail'),
        };
        const pregnancyForm = $('pregnancy-form');
        const pregnancyDate = $('pregnancy-date');
        const pregnancyDateLabel = $('pregnancy-date-label');
        const error = $('error');
        const result = $('result');
        const pregnancyResult = $('pregnancy-result');
        const share = $('share');
        const announce = $('announce');
        const out = {
            weeks: $('age-weeks'),
            calendar: $('age-calendar'),
            total: $('age-total'),
            bornAt: $('born-at'),
            milestones: $('milestones'),
        };
        const preg = {
            duration: $('pregnancy-duration'),
            detail: $('pregnancy-detail'),
            due: $('pregnancy-due'),
            countdown: $('pregnancy-countdown'),
            progress: $('pregnancy-progress'),
            progressText: $('pregnancy-progress-text'),
            milestones: $('pregnancy-milestones'),
        };
        const shareButton = $('share-link');
        const copyButton = $('copy-text');
        const shareStatus = $('share-status');
        let statusTimer = null;
        let timer = null;
        let milestonesDay = null;
        let mode = 'baby';
        let current = null; // what is shown: { mode: 'baby', birth } or { mode: 'pregnancy', lmp }
        let children = [];
        let activeId = null; // null: a new child is being entered

        function activeChild() {
            return children.find((c) => c.id === activeId) || null;
        }

        function saveChildren() {
            store(CHILDREN_KEY, children);
            store(ACTIVE_CHILD_KEY, activeId);
        }

        function renderChildren() {
            childrenBox.hidden = children.length === 0;
            removeChildButton.hidden = activeChild() === null;
            childList.replaceChildren(...children.map((child, index) => {
                const label = document.createElement('label');
                label.className = 'chip';
                const input = document.createElement('input');
                input.type = 'radio';
                input.name = 'child';
                input.value = String(child.id);
                input.checked = child.id === activeId;
                input.addEventListener('change', () => selectChild(child.id));
                label.append(input, childLabel(child, index, lang));
                return label;
            }));
        }

        function selectChild(id) {
            activeId = id;
            const child = activeChild();
            store(ACTIVE_CHILD_KEY, activeId);
            nameInput.value = child ? child.name : '';
            dateInput.value = child ? child.date : '';
            timeInput.value = child ? child.time : '';
            dueInput.value = child ? child.due : '';
            premature.open = Boolean(dueInput.value);
            renderChildren();
            if (child) {
                calculate();
            } else {
                error.hidden = true;
                hideResults();
            }
        }


        // "Today" moves on while the page or installed app stays open, so the date limits are
        // refreshed whenever a date field is used and when the app comes back to the foreground
        function refreshDateLimits() {
            dateInput.max = todayValue();
            updateBasis();
        }
        [dateInput, pregnancyDate].forEach((input) => {
            input.addEventListener('focus', refreshDateLimits);
            input.addEventListener('click', refreshDateLimits);
        });
        document.addEventListener('visibilitychange', () => document.visibilityState === 'visible' && refreshDateLimits());

        function basis() {
            return document.querySelector('input[name="basis"]:checked').value;
        }

        function hideResults() {
            clearInterval(timer);
            current = null;
            result.hidden = true;
            pregnancyResult.hidden = true;
            share.hidden = true;
        }

        function showError(message) {
            hideResults();
            error.textContent = message;
            error.hidden = false;
        }

        function show(section) {
            error.hidden = true;
            result.hidden = section !== result;
            pregnancyResult.hidden = section !== pregnancyResult;
            share.hidden = false;
        }

        function renderMilestoneList(list, items) {
            list.replaceChildren(...items.map((m) => {
                const li = document.createElement('li');
                li.className = m.daysLeft === 0 ? 'milestone is-today' : 'milestone';
                const label = document.createElement('span');
                label.className = 'milestone-label';
                label.textContent = m.label;
                const when = document.createElement('span');
                when.className = 'milestone-when';
                const time = document.createElement('time');
                time.dateTime = isoDate(m.date);
                time.textContent = formatDate(m.date, lang);
                when.append(time, ` · ${countdown(m.daysLeft, lang)}`);
                li.append(label, when);
                return li;
            }));
        }

        function renderCorrected(birth, due, now, age) {
            corrected.card.hidden = due === null;
            if (due === null) return;
            const c = correctedAge(birth, due, now);
            const gestation = t.gestationAtBirth(c.gestationWeeks, c.gestationDays);
            if (!c.premature) {
                corrected.value.textContent = t.correctedNotNeeded;
                corrected.detail.textContent = gestation;
            } else if (!c.started) {
                corrected.value.textContent = t.correctedStarts;
                corrected.detail.textContent =
                    `${t.correctedStartsIn(countdown(c.daysUntilDue, lang), formatDate(due, lang))} · ${gestation}`;
            } else {
                corrected.value.textContent = joinParts([[c.age.years, 'year'], [c.age.months, 'month'], [c.age.days, 'day']], lang);
                const parts = [joinParts([[c.age.weeks, 'week'], [c.age.weekDays, 'day']], lang), gestation];
                if (age.years >= 2) parts.push(t.correctedUntil2);
                corrected.detail.textContent = parts.join(' · ');
            }
        }

        function render(birth, due = null) {
            const now = Math.max(wallClockNow(), birth);
            // Milestones only change at midnight
            if (startOfDay(now) !== milestonesDay) {
                milestonesDay = startOfDay(now);
                renderMilestoneList(out.milestones, upcomingMilestones(birth, now, 3, lang));
            }
            const age = calculateAge(birth, now, Date.now() - wallToReal(birth));
            out.weeks.textContent = joinParts([[age.weeks, 'week'], [age.weekDays, 'day']], lang);
            out.calendar.textContent = joinParts([[age.years, 'year'], [age.months, 'month'], [age.days, 'day']], lang);
            out.total.textContent = joinParts([[age.elapsedDays, 'day'], [age.hours, 'hour'],
                [age.minutes, 'minute'], [age.seconds, 'second']], lang);
            renderCorrected(birth, due, now, age);
            return age;
        }

        function renderPregnancy(lmp) {
            const now = wallClockNow();
            if (startOfDay(now) === milestonesDay) return; // everything here changes once a day
            milestonesDay = startOfDay(now);
            const status = pregnancyStatus(lmp, now);
            preg.duration.textContent = joinParts([[status.weeks, 'week'], [status.weekDays, 'day']], lang);
            // Non-breaking spaces keep "3. tromjesečje" / "third trimester" together when the line wraps
            preg.detail.textContent = t.pregnancyDetail(status);
            preg.due.textContent = formatDate(status.due, lang);
            preg.due.dateTime = isoDate(status.due);
            preg.countdown.textContent = dueCountdown(status.daysToDue, lang);
            preg.progress.value = status.progress;
            preg.progressText.textContent = t.progress(Math.round(status.progress / PREGNANCY_DAYS * 100));
            renderMilestoneList(preg.milestones, pregnancyMilestones(lmp, now, 3, lang));
        }

        function calculate() {
            const birth = parseBirth(dateInput.value, timeInput.value);
            if (!dateInput.value) return showError(t.errors.birthMissing);
            if (birth === null) return showError(t.errors.birthInvalid);
            if (birth > wallClockNow()) return showError(t.errors.birthFuture);
            const due = dueInput.value ? parseBirth(dueInput.value, '') : null;
            if (dueInput.value && due === null) return showError(t.errors.dueInvalid);
            const dueProblem = due === null ? null : correctedAgeError(birth, due, lang);
            if (dueProblem) return showError(dueProblem);

            const entry = { name: nameInput.value, date: dateInput.value, time: timeInput.value, due: dueInput.value };
            if (activeChild()) {
                children = children.map((c) => (c.id === activeId ? cleanChild({ ...c, ...entry }) : c));
            } else {
                activeId = nextChildId(children);
                children = [...children, cleanChild({ id: activeId, ...entry })];
            }
            saveChildren();
            renderChildren();
            show(result);
            out.bornAt.textContent = `${t.born}: ${formatBirth(birth, Boolean(timeInput.value), lang)}`;
            // Named children get a visible heading; otherwise it stays for screen readers only
            const named = activeChild().name;
            resultTitle.textContent = named || t.childAgeHeading;
            resultTitle.classList.toggle('visually-hidden', !named);

            current = { mode: 'baby', birth };
            milestonesDay = null;
            render(birth, due);
            announce.textContent = `${named || t.age}: ${out.calendar.textContent}, ${t.or} ${out.weeks.textContent}.`;

            clearInterval(timer);
            timer = setInterval(() => render(birth, due), 1000);
        }

        function calculatePregnancy() {
            const date = parseBirth(pregnancyDate.value, '');
            if (!pregnancyDate.value) return showError(t.errors.dateMissing);
            if (date === null) return showError(t.errors.dateInvalid);
            const lmp = lmpFrom(basis(), date);
            const problem = pregnancyError(basis(), lmp, wallClockNow(), lang);
            if (problem) return showError(problem);

            store(PREGNANCY_KEY, { basis: basis(), date: pregnancyDate.value });
            show(pregnancyResult);

            current = { mode: 'pregnancy', lmp };
            milestonesDay = null;
            renderPregnancy(lmp);
            announce.textContent = `${t.pregnancy}: ${preg.duration.textContent}, ${t.dueDate.toLowerCase()} ${preg.due.textContent}`;

            clearInterval(timer);
            timer = setInterval(() => renderPregnancy(lmp), 60 * 1000);
        }

        function updateBasis() {
            const today = parseBirth(todayValue(), '');
            if (basis() === 'lmp') {
                pregnancyDateLabel.textContent = t.dateLabel.lmp;
                pregnancyDate.min = isoDate(today - 42 * 7 * DAY);
                pregnancyDate.max = isoDate(today);
            } else {
                pregnancyDateLabel.textContent = t.dateLabel.due;
                pregnancyDate.min = isoDate(today - 14 * DAY);
                pregnancyDate.max = isoDate(today + PREGNANCY_DAYS * DAY);
            }
        }

        function setMode(next, recalculate = true) {
            mode = next;
            store(MODE_KEY, mode);
            modeInputs.forEach((input) => { input.checked = input.value === mode; });
            form.hidden = mode !== 'baby';
            pregnancyForm.hidden = mode !== 'pregnancy';
            error.hidden = true;
            hideResults();
            if (!recalculate) return;
            if (mode === 'baby' && dateInput.value) calculate();
            if (mode === 'pregnancy' && pregnancyDate.value) calculatePregnancy();
        }

        function summary() {
            if (current && current.mode === 'pregnancy') {
                const status = pregnancyStatus(current.lmp, wallClockNow());
                const due = preg.due.textContent;
                return `${t.pregnancy}: ${preg.duration.textContent} (${t.week(status.week)}). ${t.dueDate}: ${due}${due.endsWith('.') ? '' : '.'}`;
            }
            const born = out.bornAt.textContent;
            const child = activeChild();
            const prefix = `${child && child.name ? child.name : t.age}: `;
            // The corrected age is added only when it is a real age (born early, due date passed)
            const correctedText = !corrected.card.hidden && /\d/.test(corrected.value.textContent)
                ? ` ${t.corrected}: ${corrected.value.textContent}.` : '';
            return `${prefix}${out.calendar.textContent} (${out.weeks.textContent}).${correctedText} ${born}${born.endsWith('.') ? '' : '.'}`;
        }

        function shareUrl() {
            const base = location.origin + location.pathname;
            if (current && current.mode === 'pregnancy') {
                return `${base}#t=${isoDate(current.lmp + PREGNANCY_DAYS * DAY)}`;
            }
            const child = activeChild();
            return buildShareUrl(base, dateInput.value, timeInput.value, child ? child.name : '', child ? child.due : '');
        }

        function showStatus(message) {
            clearTimeout(statusTimer);
            shareStatus.textContent = message;
            statusTimer = setTimeout(() => { shareStatus.textContent = ''; }, 4000);
        }

        async function copy(text) {
            try {
                await navigator.clipboard.writeText(text);
                return true;
            } catch (e) {
                // Older browsers: copy from a temporary textarea
                const area = document.createElement('textarea');
                area.value = text;
                area.setAttribute('readonly', '');
                area.className = 'visually-hidden';
                document.body.append(area);
                area.select();
                const ok = document.execCommand('copy');
                area.remove();
                return ok;
            }
        }

        shareButton.addEventListener('click', async function () {
            const url = shareUrl();
            if (navigator.share) {
                try {
                    await navigator.share({ title: 'Baby Calculator', text: summary(), url });
                    return;
                } catch (e) {
                    if (e.name === 'AbortError') return;
                }
            }
            showStatus(await copy(url) ? t.linkCopied : t.copyFailed);
        });

        copyButton.addEventListener('click', async function () {
            showStatus(await copy(summary()) ? t.textCopied : t.copyFailed);
        });

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            calculate();
        });
        dateInput.addEventListener('change', () => dateInput.value && calculate());
        nameInput.addEventListener('input', function () {
            const child = activeChild();
            if (!child) return; // a new child gets its name when it is calculated
            children = children.map((c) => (c.id === activeId ? cleanChild({ ...c, name: nameInput.value }) : c));
            saveChildren();
            renderChildren();
            if (!result.hidden) {
                const named = activeChild().name;
                resultTitle.textContent = named || t.childAgeHeading;
                resultTitle.classList.toggle('visually-hidden', !named);
            }
        });
        addChildButton.addEventListener('click', function () {
            selectChild(null);
            nameInput.focus();
        });
        removeChildButton.addEventListener('click', function () {
            const child = activeChild();
            if (!child) return;
            if (!confirm(t.confirmRemove(childLabel(child, children.indexOf(child), lang)))) return;
            const next = removeChild(children, child.id);
            children = next.children;
            saveChildren();
            selectChild(next.activeId);
        });
        timeInput.addEventListener('change', () => dateInput.value && calculate());
        dueInput.addEventListener('change', () => dateInput.value && calculate());

        pregnancyForm.addEventListener('submit', function (event) {
            event.preventDefault();
            calculatePregnancy();
        });
        pregnancyDate.addEventListener('change', () => pregnancyDate.value && calculatePregnancy());
        basisInputs.forEach((input) => input.addEventListener('change', function () {
            // Keep the same pregnancy: convert the entered date to the other basis
            const date = parseBirth(pregnancyDate.value, '');
            if (date !== null) {
                pregnancyDate.value = isoDate(basis() === 'lmp' ? date - PREGNANCY_DAYS * DAY : date + PREGNANCY_DAYS * DAY);
            }
            updateBasis();
            if (pregnancyDate.value) calculatePregnancy();
        }));
        modeInputs.forEach((input) => input.addEventListener('change', () => setMode(input.value)));

        // Shared links are saved like normal entries, so they aren't needed after this
        children = loadChildren();
        const savedActive = restore(ACTIVE_CHILD_KEY);
        activeId = children.some((c) => c.id === savedActive) ? savedActive : (children[0] ? children[0].id : null);
        function takeShareLink() {
            const source = `${location.search}${location.hash}`;
            const sharedBirth = readSharedBirth(source);
            const sharedPregnancy = sharedBirth ? null : readSharedPregnancy(source);
            if (sharedBirth) {
                // Added next to the visitor's own children (or selected if already there), never overwriting them
                ({ children, activeId } = addSharedChild(children, sharedBirth));
                saveChildren();
                store(MODE_KEY, 'baby');
            } else if (sharedPregnancy) {
                store(PREGNANCY_KEY, sharedPregnancy);
                store(MODE_KEY, 'pregnancy');
            }
            if (/[?&#][dt]=/.test(source)) history.replaceState(null, '', location.pathname);
            return Boolean(sharedBirth || sharedPregnancy);
        }
        takeShareLink();

        // Offline support and installing as an app
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js').catch(() => { /* the page works without it */ });
        }
        const installButton = $('install-app');
        let installPrompt = null;
        window.addEventListener('beforeinstallprompt', function (event) {
            // Chrome/Android: offer our own button instead of the browser's mini-infobar
            event.preventDefault();
            installPrompt = event;
            installButton.hidden = false;
        });
        installButton.addEventListener('click', async function () {
            installButton.hidden = true;
            if (!installPrompt) return;
            installPrompt.prompt();
            await installPrompt.userChoice;
            installPrompt = null;
        });
        window.addEventListener('appinstalled', () => { installButton.hidden = true; });

        // --- Backup and restore ---
        const backupBox = $('backup');
        const backupStatus = $('backup-status');
        const backupFile = $('backup-file');

        function currentBackup() {
            return makeBackup({ children, activeChild: activeId, pregnancy: restore(PREGNANCY_KEY), mode },
                new Date().toISOString());
        }

        // Merges a backup into the saved data and returns the message to show
        function applyBackup(backup) {
            const merged = mergeChildren(children, backup.children);
            children = merged.children;
            if (activeChild() === null && children.length) activeId = children[0].id;
            saveChildren();
            let pregnancyChanged = false;
            if (backup.pregnancy) {
                const local = restore(PREGNANCY_KEY);
                const same = local && local.basis === backup.pregnancy.basis && local.date === backup.pregnancy.date;
                if (!same && (!local || !local.date || confirm(t.backupReplacePregnancy))) {
                    store(PREGNANCY_KEY, backup.pregnancy);
                    pregnancyChanged = true;
                }
            }
            if (!merged.added && !merged.changed && !pregnancyChanged) return t.backupNothingNew;
            // Show what was restored
            store(MODE_KEY, merged.added || merged.changed || !pregnancyChanged ? 'baby' : 'pregnancy');
            return t.backupRestored;
        }

        function downloadFile(name, content, type) {
            const link = document.createElement('a');
            link.href = URL.createObjectURL(new Blob([content], { type }));
            link.download = name;
            document.body.append(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(link.href), 1000);
        }

        $('backup-download').addEventListener('click', function () {
            downloadFile(`baby-calculator-${todayValue()}.json`, JSON.stringify(currentBackup(), null, 2), 'application/json');
        });

        // Calendar export of the milestones (.ics)
        const site = location.origin + location.pathname;
        $('calendar-baby').addEventListener('click', function () {
            const child = activeChild();
            if (!child || !current || current.mode !== 'baby') return;
            const label = childLabel(child, children.indexOf(child), lang);
            const events = babyCalendarEvents(current.birth, label, wallClockNow(), lang, site);
            downloadFile(`baby-calculator-${child.date}.ics`, buildIcs(events, Date.now()), 'text/calendar');
        });
        $('calendar-pregnancy').addEventListener('click', function () {
            if (!current || current.mode !== 'pregnancy') return;
            const events = pregnancyCalendarEvents(current.lmp, wallClockNow(), lang, site);
            downloadFile(`baby-calculator-pregnancy-${isoDate(current.lmp + PREGNANCY_DAYS * DAY)}.ics`,
                buildIcs(events, Date.now()), 'text/calendar');
        });
        $('backup-restore').addEventListener('click', () => backupFile.click());
        backupFile.addEventListener('change', async function () {
            const file = backupFile.files[0];
            backupFile.value = '';
            if (!file) return;
            if (file.size > BACKUP_MAX_BYTES) {
                backupStatus.textContent = t.backupTooLarge;
                return;
            }
            const backup = parseBackup(await file.text());
            if (!backup) {
                backupStatus.textContent = t.backupInvalid;
                return;
            }
            backupStatus.textContent = applyBackup(backup);
            showSaved();
        });
        $('backup-link').addEventListener('click', async function () {
            const ok = await copy(buildBackupLink(location.origin + location.pathname, currentBackup()));
            backupStatus.textContent = ok ? t.backupLinkCopied : t.copyFailed;
        });

        // A transfer link (#backup=...) is merged once and then removed from the address bar
        function takeBackupLink() {
            if (!/^#backup=/.test(location.hash)) return null;
            const linked = readBackupLink(location.hash);
            history.replaceState(null, '', location.pathname + location.search);
            return linked ? applyBackup(linked) : t.backupInvalid;
        }
        const backupMessage = takeBackupLink();

        // Fills the forms from the saved data and shows the saved mode
        function showSaved() {
            const child = activeChild();
            nameInput.value = child ? child.name : '';
            dateInput.value = child ? child.date : '';
            timeInput.value = child ? child.time : '';
            dueInput.value = child ? child.due : '';
            premature.open = Boolean(dueInput.value);
            store(ACTIVE_CHILD_KEY, activeId);
            renderChildren();
            const savedPregnancy = restore(PREGNANCY_KEY);
            if (savedPregnancy && savedPregnancy.date) {
                basisInputs.forEach((input) => { input.checked = input.value === savedPregnancy.basis; });
                pregnancyDate.value = savedPregnancy.date;
            }
            refreshDateLimits();
            setMode(restore(MODE_KEY) === 'pregnancy' ? 'pregnancy' : 'baby');
        }

        function showBackupMessage(message) {
            if (!message) return;
            backupBox.open = true;
            backupStatus.textContent = message;
        }

        showSaved();
        showBackupMessage(backupMessage);
        // A share or transfer link opened while the page is already open only changes the "#" part
        window.addEventListener('hashchange', function () {
            if (takeShareLink()) {
                showSaved();
                return;
            }
            const message = takeBackupLink();
            if (!message) return;
            showSaved();
            showBackupMessage(message);
        });
    });

    // Exposed for tests
    if (typeof module !== 'undefined') {
        module.exports = {
            plural, FORMS, joinParts, parseBirth, addMonths, calculateAge, upcomingMilestones, countdown, formatDate,
            readSharedBirth, buildShareUrl, lmpFrom, pregnancyStatus, pregnancyError, pregnancyMilestones, dueCountdown,
            readSharedPregnancy, normalizeChildren, nextChildId, childLabel, addSharedChild, removeChild,
            babyMilestones, icsEscape, icsFold, buildIcs, babyCalendarEvents, pregnancyCalendarEvents,
            correctedAge, correctedAgeError, makeBackup, parseBackup, mergeChildren, buildBackupLink, readBackupLink,
            TEXT, unit, formatBirth,
        };
    }
})();
