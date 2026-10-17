// Date math: age, corrected age, pregnancy and milestones. All math uses wall-clock time stored
// as UTC milliseconds (see wallClockNow).
// Shared through the BC namespace; loaded before app.js (see templates/index.html).
(function (BC) {
    'use strict';

    const {
        pad, texts, unit,
    } = BC;

    const DAY = 24 * 60 * 60 * 1000;
    const DAY_MILESTONES = [100, 200, 300, 500, 1000, 2000, 3000, 5000, 10000];
    const PREGNANCY_DAYS = 280; // due date = first day of the last period + 280 days (Naegele's rule)
    const PREGNANCY_MILESTONES = [[14, 'second'], [20, 'half'], [28, 'third'], [37, 'term'], [40, 'due']];

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
        return t.inDays(daysLeft);
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

    const PREGNANCY_BASES = ['due', 'lmp', 'ivf', 'ultrasound'];
    const EMBRYO_DAYS = [3, 5, 6];

    // The first day of the last period (LMP), in ms, from what is known:
    //   due        due date − 280 days
    //   lmp        the date itself
    //   ivf        transfer date − 14 days − embryo age (3, 5 or 6 days); day 5 gives due = transfer + 261
    //   ultrasound scan date − gestational age measured at the scan
    function lmpFrom(basis, dateMs, extra = {}) {
        switch (basis) {
            case 'lmp': return dateMs;
            case 'ivf': return dateMs - (14 + extra.embryoDays) * DAY;
            case 'ultrasound': return dateMs - (extra.gaWeeks * 7 + extra.gaDays) * DAY;
            default: return dateMs - PREGNANCY_DAYS * DAY;
        }
    }

    // A pregnancy as stored: { basis, date, embryoDays?, gaWeeks?, gaDays? }; null if incomplete or invalid
    function validPregnancy(p) {
        if (!p || !PREGNANCY_BASES.includes(p.basis) || parseBirth(p.date, '') === null) return null;
        const state = { basis: p.basis, date: p.date };
        if (p.basis === 'ivf') {
            if (!EMBRYO_DAYS.includes(p.embryoDays)) return null;
            state.embryoDays = p.embryoDays;
        }
        if (p.basis === 'ultrasound') {
            const weeks = p.gaWeeks;
            const days = p.gaDays;
            if (!Number.isInteger(weeks) || !Number.isInteger(days) || weeks < 0 || weeks > 42 || days < 0 || days > 6) {
                return null;
            }
            Object.assign(state, { gaWeeks: weeks, gaDays: days });
        }
        return state;
    }

    function pregnancyLmp(state) {
        return lmpFrom(state.basis, parseBirth(state.date, ''), state);
    }

    // The same pregnancy described with another basis (switching the radio buttons keeps the result)
    function convertPregnancy(state, basis, now) {
        const lmp = pregnancyLmp(state);
        if (basis === 'due') return { basis, date: isoDate(lmp + PREGNANCY_DAYS * DAY) };
        if (basis === 'lmp') return { basis, date: isoDate(lmp) };
        if (basis === 'ivf') {
            const embryoDays = state.embryoDays || 5;
            return { basis, date: isoDate(lmp + (14 + embryoDays) * DAY), embryoDays };
        }
        // Ultrasound: keep a scan that was entered, otherwise a scan today with the matching age
        const scan = state.basis === 'ultrasound' ? parseBirth(state.date, '') : startOfDay(now);
        const age = Math.min(Math.max(Math.round((scan - lmp) / DAY), 0), 42 * 7 + 6);
        return { basis, date: isoDate(scan), gaWeeks: Math.floor(age / 7), gaDays: age % 7 };
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
    // eventDate: the entered date (period, transfer or scan), which can't be in the future
    function pregnancyError(basis, lmp, now, lang = 'hr', eventDate = lmp) {
        const errors = texts(lang).errors;
        const today = startOfDay(now);
        if (basis !== 'due' && eventDate > today) return basis === 'lmp' ? errors.lmpFuture : errors.dateFuture;
        const days = Math.round((today - lmp) / DAY);
        if (days < 0) return basis === 'due' ? errors.dueTooFar : errors.dateFuture;
        if (days > 42 * 7) {
            return { due: errors.duePassed, lmp: errors.lmpTooOld }[basis] || errors.pregnancyTooOld;
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

    function dueCountdown(daysToDue, lang = 'hr') {
        if (daysToDue < 0) return texts(lang).ago(-daysToDue);
        return countdown(daysToDue, lang);
    }

    Object.assign(BC, {
        DAY, DAY_MILESTONES, PREGNANCY_DAYS, PREGNANCY_MILESTONES, wallClockNow, parseBirth, addMonths,
        wallToReal, calculateAge, MAX_DAYS_EARLY, correctedAge, correctedAgeError, startOfDay, babyMilestones,
        upcomingMilestones, countdown, formatDate, formatBirth, todayValue, isoDate, PREGNANCY_BASES,
        EMBRYO_DAYS, lmpFrom, validPregnancy, pregnancyLmp, convertPregnancy, pregnancyStatus, pregnancyError,
        pregnancyMilestones, dueCountdown,
    });
})(globalThis.BC = globalThis.BC || {});
