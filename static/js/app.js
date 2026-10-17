(function () {
    'use strict';

    const STORAGE_KEY = 'birth';
    const LEGACY_COOKIE = 'datetime';
    const DAY = 24 * 60 * 60 * 1000;
    const DAY_MILESTONES = [100, 200, 300, 500, 1000, 2000, 3000, 5000, 10000];

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

    function unit(n, key) {
        return `${n} ${plural(n, FORMS[key])}`;
    }

    // "a", "a i b", "a, b i c"; zero parts are left out unless all are zero
    function joinParts(parts) {
        const shown = parts.filter(([n]) => n > 0);
        const list = (shown.length ? shown : parts.slice(-1)).map(([n, key]) => unit(n, key));
        if (list.length === 1) return list[0];
        return `${list.slice(0, -1).join(', ')} i ${list[list.length - 1]}`;
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

    function calculateAge(birth, now) {
        const b = new Date(birth);
        const n = new Date(now);
        let months = (n.getUTCFullYear() - b.getUTCFullYear()) * 12 + n.getUTCMonth() - b.getUTCMonth();
        if (addMonths(birth, months) > now) months--;

        const diff = now - birth;
        const totalDays = Math.floor(diff / DAY);
        return {
            years: Math.floor(months / 12),
            months: months % 12,
            days: Math.floor((now - addMonths(birth, months)) / DAY),
            weeks: Math.floor(totalDays / 7),
            weekDays: totalDays % 7,
            totalDays,
            hours: Math.floor(diff / 3600000) % 24,
            minutes: Math.floor(diff / 60000) % 60,
            seconds: Math.floor(diff / 1000) % 60,
        };
    }

    function startOfDay(ms) {
        const d = new Date(ms);
        return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
    }

    // Upcoming month birthdays (1–23 months), birthdays and day counts, nearest first.
    // Dates only: a milestone is "today" for the whole day.
    function upcomingMilestones(birth, now, count = 3) {
        const birthDay = startOfDay(birth);
        const today = startOfDay(now);
        const all = DAY_MILESTONES.map((n) => ({ date: birthDay + n * DAY, label: unit(n, 'day') }));
        for (let m = 1; m < 24; m++) {
            if (m % 12) all.push({ date: addMonths(birthDay, m), label: unit(m, 'month') });
        }
        for (let y = 1; y <= 120; y++) {
            all.push({ date: addMonths(birthDay, y * 12), label: `${y}. rođendan` });
        }
        return all
            .filter((m) => m.date >= today)
            .sort((a, b) => a.date - b.date)
            .slice(0, count)
            .map((m) => ({ ...m, daysLeft: Math.round((m.date - today) / DAY) }));
    }

    function countdown(daysLeft) {
        if (daysLeft === 0) return 'danas';
        if (daysLeft === 1) return 'sutra';
        return `za ${unit(daysLeft, 'day')}`;
    }

    function formatDate(ms) {
        const d = new Date(ms);
        const pad = (n) => String(n).padStart(2, '0');
        return `${pad(d.getUTCDate())}.${pad(d.getUTCMonth() + 1)}.${d.getUTCFullYear()}.`;
    }

    function formatBirth(ms, hasTime) {
        const d = new Date(ms);
        const pad = (n) => String(n).padStart(2, '0');
        const date = formatDate(ms);
        return hasTime ? `${date} u ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}` : date;
    }

    function todayValue() {
        const d = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }

    // ?d=YYYY-MM-DD or ?d=YYYY-MM-DDTHH:MM
    function readSharedBirth(search) {
        const match = /[?&]d=([^&#]*)/.exec(search || '');
        if (!match) return null;
        const [date, time = ''] = decodeURIComponent(match[1]).split('T');
        return parseBirth(date, time) === null ? null : { date, time };
    }

    function buildShareUrl(base, date, time) {
        return `${base}?d=${date}${time ? `T${time}` : ''}`;
    }

    function load() {
        try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
            if (saved && saved.date) return saved;
        } catch (e) { /* storage unavailable */ }

        // v1.x kept "YYYY-MM-DDTHH:MM" in a cookie; move it to localStorage once
        const match = document.cookie.match(new RegExp(`(?:^|; )${LEGACY_COOKIE}=([^;]*)`));
        if (match) {
            document.cookie = `${LEGACY_COOKIE}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
            const [date, time] = decodeURIComponent(match[1]).split('T');
            const saved = { date, time: time || '' };
            save(saved);
            return saved;
        }
        return null;
    }

    function save(value) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
        } catch (e) { /* storage unavailable */ }
    }

    if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', function () {
        const form = document.getElementById('birth-form');
        const dateInput = document.getElementById('birth-date');
        const timeInput = document.getElementById('birth-time');
        const error = document.getElementById('error');
        const result = document.getElementById('result');
        const announce = document.getElementById('announce');
        const out = {
            weeks: document.getElementById('age-weeks'),
            calendar: document.getElementById('age-calendar'),
            total: document.getElementById('age-total'),
            bornAt: document.getElementById('born-at'),
            milestones: document.getElementById('milestones'),
        };
        const shareButton = document.getElementById('share-link');
        const copyButton = document.getElementById('copy-text');
        const shareStatus = document.getElementById('share-status');
        let statusTimer = null;
        let timer = null;
        let milestonesDay = null;

        dateInput.max = todayValue();

        function showError(message) {
            clearInterval(timer);
            result.hidden = true;
            error.textContent = message;
            error.hidden = false;
        }

        function renderMilestones(birth, now) {
            const items = upcomingMilestones(birth, now).map((m) => {
                const li = document.createElement('li');
                li.className = m.daysLeft === 0 ? 'milestone is-today' : 'milestone';
                const label = document.createElement('span');
                label.className = 'milestone-label';
                label.textContent = m.label;
                const when = document.createElement('span');
                when.className = 'milestone-when';
                const time = document.createElement('time');
                time.dateTime = new Date(m.date).toISOString().slice(0, 10);
                time.textContent = formatDate(m.date);
                when.append(time, ` · ${countdown(m.daysLeft)}`);
                li.append(label, when);
                return li;
            });
            out.milestones.replaceChildren(...items);
        }

        function render(birth) {
            const now = Math.max(wallClockNow(), birth);
            // Milestones only change at midnight
            if (startOfDay(now) !== milestonesDay) {
                milestonesDay = startOfDay(now);
                renderMilestones(birth, now);
            }
            const age = calculateAge(birth, now);
            out.weeks.textContent = joinParts([[age.weeks, 'week'], [age.weekDays, 'day']]);
            out.calendar.textContent = joinParts([[age.years, 'year'], [age.months, 'month'], [age.days, 'day']]);
            out.total.textContent = joinParts([[age.totalDays, 'day'], [age.hours, 'hour'],
                [age.minutes, 'minute'], [age.seconds, 'second']]);
            return age;
        }

        function calculate() {
            const birth = parseBirth(dateInput.value, timeInput.value);
            if (!dateInput.value) return showError('Unesite datum rođenja.');
            if (birth === null) return showError('Neispravan datum ili vrijeme rođenja.');
            if (birth > wallClockNow()) return showError('Datum rođenja ne može biti u budućnosti.');

            save({ date: dateInput.value, time: timeInput.value });
            error.hidden = true;
            result.hidden = false;
            out.bornAt.textContent = `Rođenje: ${formatBirth(birth, Boolean(timeInput.value))}`;

            milestonesDay = null;
            render(birth);
            announce.textContent = `Dob: ${out.calendar.textContent}, odnosno ${out.weeks.textContent}.`;

            clearInterval(timer);
            timer = setInterval(() => render(birth), 1000);
        }

        function summary() {
            const born = out.bornAt.textContent;
            return `Dob: ${out.calendar.textContent} (${out.weeks.textContent}). ${born}${born.endsWith('.') ? '' : '.'}`;
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
            const url = buildShareUrl(location.origin + location.pathname, dateInput.value, timeInput.value);
            if (navigator.share) {
                try {
                    await navigator.share({ title: 'Baby Calculator', text: summary(), url });
                    return;
                } catch (e) {
                    if (e.name === 'AbortError') return;
                }
            }
            showStatus(await copy(url) ? 'Poveznica je kopirana.' : 'Kopiranje nije uspjelo.');
        });

        copyButton.addEventListener('click', async function () {
            showStatus(await copy(summary()) ? 'Tekst je kopiran.' : 'Kopiranje nije uspjelo.');
        });

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            calculate();
        });
        dateInput.addEventListener('change', () => dateInput.value && calculate());
        timeInput.addEventListener('change', () => dateInput.value && calculate());

        const shared = readSharedBirth(location.search);
        if (shared) {
            // The shared date is saved like a normal entry, so the link isn't needed after this
            save(shared);
            history.replaceState(null, '', location.pathname + location.hash);
        }

        // Offline support and installing as an app
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js').catch(() => { /* the page works without it */ });
        }
        const installButton = document.getElementById('install-app');
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

        const saved = load();
        if (saved) {
            dateInput.value = saved.date;
            timeInput.value = saved.time || '';
            calculate();
        }
    });

    // Exposed for tests
    if (typeof module !== 'undefined') {
        module.exports = { plural, FORMS, joinParts, parseBirth, addMonths, calculateAge, upcomingMilestones, countdown, formatDate, readSharedBirth, buildShareUrl };
    }
})();
