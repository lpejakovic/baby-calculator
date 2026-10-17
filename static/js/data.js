// Children, share links and backups: pure data handling, no DOM or storage.
// Shared through the BC namespace; loaded before app.js (see templates/index.html).
(function (BC) {
    'use strict';

    const {
        cleanMeasurements, parseBirth, texts, validPregnancy,
    } = BC;

    const NAME_MAX = 40;

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
        const clean = {
            id: child.id,
            name: String(child.name || '').trim().slice(0, NAME_MAX),
            date: child.date,
            time: child.time || '',
            // Due date for the corrected age of a premature baby; '' when not given
            due: typeof child.due === 'string' && parseBirth(child.due, '') !== null ? child.due : '',
        };
        // Growth chart data, stored only once used: sex ('f' or 'm') and measurements
        if (child.sex === 'f' || child.sex === 'm') clean.sex = child.sex;
        const measurements = cleanMeasurements(child.measurements);
        if (measurements.length) clean.measurements = measurements;
        return clean;
    }

    // Valid children from storage or a backup
    function normalizeChildren(stored) {
        const valid = (c) => c && typeof c.date === 'string' && parseBirth(c.date, c.time || '') !== null;
        const list = Array.isArray(stored) ? stored.filter(valid) : [];
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
                sex: c.sex || shared.sex,
                // Measurements from both; on the same date the existing ones win
                measurements: cleanMeasurements([...(shared.measurements || []), ...(c.measurements || [])]),
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
            children: normalizeChildren(data.children),
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

    const BACKUP_REMIND_DAYS = 30;  // remind when the last backup is older than this
    const BACKUP_SNOOZE_DAYS = 7;   // "Kasnije" hides the reminder for this long

    // Days between two "YYYY-MM-DD" dates (b - a)
    function daysBetween(a, b) {
        const utc = (d) => Date.UTC(Number(d.slice(0, 4)), Number(d.slice(5, 7)) - 1, Number(d.slice(8, 10)));
        return Math.round((utc(b) - utc(a)) / 86400000);
    }

    // Whether to remind about a backup. Data is only in this browser (Safari clears it after about a week
    // without a visit), so: something is saved, not just today, and no backup in the last 30 days, unless
    // the visitor chose "Kasnije" less than a week ago. All dates are "YYYY-MM-DD" or null.
    function backupReminderDue({ hasData, firstSaved, lastBackup, snoozed, today }) {
        if (!hasData || !firstSaved || firstSaved >= today) return false;
        if (lastBackup && daysBetween(lastBackup, today) < BACKUP_REMIND_DAYS) return false;
        return !(snoozed && daysBetween(snoozed, today) < BACKUP_SNOOZE_DAYS);
    }

    Object.assign(BC, {
        BACKUP_REMIND_DAYS, BACKUP_SNOOZE_DAYS, daysBetween, backupReminderDue,
        NAME_MAX, readSharedPregnancy, readSharedBirth, buildShareUrl, cleanChild, normalizeChildren,
        nextChildId, childLabel, addSharedChild, BACKUP_APP, BACKUP_VERSION, BACKUP_MAX_BYTES, makeBackup,
        parseBackup, mergeChildren, buildBackupLink, readBackupLink, removeChild,
    });
})(globalThis.BC = globalThis.BC || {});
