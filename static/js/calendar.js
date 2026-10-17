// Calendar export of milestones as iCalendar (.ics, RFC 5545).
// Shared through the BC namespace; loaded before app.js (see templates/index.html).
(function (BC) {
    'use strict';

    const {
        DAY, PREGNANCY_MILESTONES, babyMilestones, isoDate, pregnancyMilestones, startOfDay, texts,
    } = BC;

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

    Object.assign(BC, {
        CALENDAR_HORIZON_DAYS, icsDate, icsEscape, icsFold, buildIcs, babyCalendarEvents,
        pregnancyCalendarEvents,
    });
})(globalThis.BC = globalThis.BC || {});
