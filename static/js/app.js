(function () {
    'use strict';

    const STORAGE_KEY = 'birth';
    const MODE_KEY = 'mode';
    const PREGNANCY_KEY = 'pregnancy';
    const LEGACY_COOKIE = 'datetime';
    const DAY = 24 * 60 * 60 * 1000;
    const DAY_MILESTONES = [100, 200, 300, 500, 1000, 2000, 3000, 5000, 10000];
    const PREGNANCY_DAYS = 280; // due date = first day of the last period + 280 days (Naegele's rule)
    const PREGNANCY_MILESTONES = [
        [14, '2. tromjesečje'],
        [20, 'Polovica trudnoće'],
        [28, '3. tromjesečje'],
        [37, 'Donošena trudnoća'],
        [40, 'Termin poroda'],
    ];

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
    function pregnancyError(basis, lmp, now) {
        const days = Math.round((startOfDay(now) - lmp) / DAY);
        if (days < 0) {
            return basis === 'lmp'
                ? 'Datum zadnje menstruacije ne može biti u budućnosti.'
                : 'Termin je predaleko u budućnosti (više od 40 tjedana).';
        }
        if (days > 42 * 7) {
            return basis === 'lmp'
                ? 'Zadnja menstruacija je prije više od 42 tjedna. Ako je beba rođena, odaberite „Beba je rođena”.'
                : 'Termin je prošao prije više od dva tjedna. Ako je beba rođena, odaberite „Beba je rođena”.';
        }
        return null;
    }

    function pregnancyMilestones(lmp, now, count = 3) {
        const today = startOfDay(now);
        return PREGNANCY_MILESTONES
            .map(([weeks, label]) => ({ date: lmp + weeks * 7 * DAY, label }))
            .filter((m) => m.date >= today)
            .slice(0, count)
            .map((m) => ({ ...m, daysLeft: Math.round((m.date - today) / DAY) }));
    }

    function dueCountdown(daysToDue) {
        if (daysToDue < 0) return `prije ${unit(-daysToDue, 'day')}`;
        return countdown(daysToDue);
    }

    // ?t=YYYY-MM-DD (due date)
    function readSharedPregnancy(search) {
        const match = /[?&]t=([^&#]*)/.exec(search || '');
        if (!match) return null;
        const date = decodeURIComponent(match[1]);
        return parseBirth(date, '') === null ? null : { basis: 'due', date };
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
        store(STORAGE_KEY, value);
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
        const modeInputs = document.querySelectorAll('input[name="mode"]');
        const basisInputs = document.querySelectorAll('input[name="basis"]');
        const form = $('birth-form');
        const dateInput = $('birth-date');
        const timeInput = $('birth-time');
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

        dateInput.max = todayValue();

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
                time.textContent = formatDate(m.date);
                when.append(time, ` · ${countdown(m.daysLeft)}`);
                li.append(label, when);
                return li;
            }));
        }

        function render(birth) {
            const now = Math.max(wallClockNow(), birth);
            // Milestones only change at midnight
            if (startOfDay(now) !== milestonesDay) {
                milestonesDay = startOfDay(now);
                renderMilestoneList(out.milestones, upcomingMilestones(birth, now));
            }
            const age = calculateAge(birth, now);
            out.weeks.textContent = joinParts([[age.weeks, 'week'], [age.weekDays, 'day']]);
            out.calendar.textContent = joinParts([[age.years, 'year'], [age.months, 'month'], [age.days, 'day']]);
            out.total.textContent = joinParts([[age.totalDays, 'day'], [age.hours, 'hour'],
                [age.minutes, 'minute'], [age.seconds, 'second']]);
            return age;
        }

        function renderPregnancy(lmp) {
            const now = wallClockNow();
            if (startOfDay(now) === milestonesDay) return; // everything here changes once a day
            milestonesDay = startOfDay(now);
            const status = pregnancyStatus(lmp, now);
            preg.duration.textContent = joinParts([[status.weeks, 'week'], [status.weekDays, 'day']]);
            // Non-breaking spaces keep "3. tromjesečje" together when the line wraps
            preg.detail.textContent = `${status.weeks}+${status.weekDays} · ${status.week}.\u00a0tjedan · ${status.trimester}.\u00a0tromjesečje`;
            preg.due.textContent = formatDate(status.due);
            preg.due.dateTime = isoDate(status.due);
            preg.countdown.textContent = dueCountdown(status.daysToDue);
            preg.progress.value = status.progress;
            preg.progressText.textContent = `${Math.round(status.progress / PREGNANCY_DAYS * 100)} % trudnoće`;
            renderMilestoneList(preg.milestones, pregnancyMilestones(lmp, now));
        }

        function calculate() {
            const birth = parseBirth(dateInput.value, timeInput.value);
            if (!dateInput.value) return showError('Unesite datum rođenja.');
            if (birth === null) return showError('Neispravan datum ili vrijeme rođenja.');
            if (birth > wallClockNow()) {
                return showError('Datum rođenja ne može biti u budućnosti. Za trudnoću odaberite „Trudnoća”.');
            }

            save({ date: dateInput.value, time: timeInput.value });
            show(result);
            out.bornAt.textContent = `Rođenje: ${formatBirth(birth, Boolean(timeInput.value))}`;

            current = { mode: 'baby', birth };
            milestonesDay = null;
            render(birth);
            announce.textContent = `Dob: ${out.calendar.textContent}, odnosno ${out.weeks.textContent}.`;

            clearInterval(timer);
            timer = setInterval(() => render(birth), 1000);
        }

        function calculatePregnancy() {
            const date = parseBirth(pregnancyDate.value, '');
            if (!pregnancyDate.value) return showError('Unesite datum.');
            if (date === null) return showError('Neispravan datum.');
            const lmp = lmpFrom(basis(), date);
            const problem = pregnancyError(basis(), lmp, wallClockNow());
            if (problem) return showError(problem);

            store(PREGNANCY_KEY, { basis: basis(), date: pregnancyDate.value });
            show(pregnancyResult);

            current = { mode: 'pregnancy', lmp };
            milestonesDay = null;
            renderPregnancy(lmp);
            announce.textContent = `Trudnoća: ${preg.duration.textContent}, termin ${preg.due.textContent}`;

            clearInterval(timer);
            timer = setInterval(() => renderPregnancy(lmp), 60 * 1000);
        }

        function updateBasis() {
            const today = parseBirth(todayValue(), '');
            if (basis() === 'lmp') {
                pregnancyDateLabel.textContent = 'Prvi dan zadnje menstruacije';
                pregnancyDate.min = isoDate(today - 42 * 7 * DAY);
                pregnancyDate.max = isoDate(today);
            } else {
                pregnancyDateLabel.textContent = 'Termin poroda';
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
                return `Trudnoća: ${preg.duration.textContent} (${status.week}. tjedan). Termin: ${preg.due.textContent}`;
            }
            const born = out.bornAt.textContent;
            return `Dob: ${out.calendar.textContent} (${out.weeks.textContent}). ${born}${born.endsWith('.') ? '' : '.'}`;
        }

        function shareUrl() {
            const base = location.origin + location.pathname;
            if (current && current.mode === 'pregnancy') {
                return `${base}?t=${isoDate(current.lmp + PREGNANCY_DAYS * DAY)}`;
            }
            return buildShareUrl(base, dateInput.value, timeInput.value);
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
        const sharedBirth = readSharedBirth(location.search);
        const sharedPregnancy = readSharedPregnancy(location.search);
        if (sharedBirth) {
            save(sharedBirth);
            store(MODE_KEY, 'baby');
        } else if (sharedPregnancy) {
            store(PREGNANCY_KEY, sharedPregnancy);
            store(MODE_KEY, 'pregnancy');
        }
        if (sharedBirth || sharedPregnancy || /[?&][dt]=/.test(location.search)) {
            history.replaceState(null, '', location.pathname + location.hash);
        }

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

        const saved = load();
        if (saved) {
            dateInput.value = saved.date;
            timeInput.value = saved.time || '';
        }
        const savedPregnancy = restore(PREGNANCY_KEY);
        if (savedPregnancy && savedPregnancy.date) {
            basisInputs.forEach((input) => { input.checked = input.value === savedPregnancy.basis; });
            pregnancyDate.value = savedPregnancy.date;
        }
        updateBasis();
        setMode(restore(MODE_KEY) === 'pregnancy' ? 'pregnancy' : 'baby');
    });

    // Exposed for tests
    if (typeof module !== 'undefined') {
        module.exports = {
            plural, FORMS, joinParts, parseBirth, addMonths, calculateAge, upcomingMilestones, countdown, formatDate,
            readSharedBirth, buildShareUrl, lmpFrom, pregnancyStatus, pregnancyError, pregnancyMilestones, dueCountdown,
            readSharedPregnancy,
        };
    }
})();
