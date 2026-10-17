// Page code: forms, results, storage and events. The pure logic is in texts.js, dates.js,
// calendar.js and data.js, loaded before this file.
(function () {
    'use strict';

    const {
        BACKUP_MAX_BYTES, DAY, PREGNANCY_DAYS, addSharedChild, babyCalendarEvents, buildBackupLink, buildIcs,
        buildShareUrl, calculateAge, childLabel, cleanChild, convertPregnancy, correctedAge, correctedAgeError,
        TEXT, countdown, drawCard, dueCountdown, formatBirth, layoutCard, formatDate, isoDate, joinParts, makeBackup, mergeChildren,
        nextChildId, normalizeChildren, parseBackup, parseBirth, pregnancyCalendarEvents, pregnancyError,
        pregnancyLmp, pregnancyMilestones, pregnancyStatus, readBackupLink, readSharedBirth,
        readSharedPregnancy, removeChild, startOfDay, texts, todayValue, upcomingMilestones, validPregnancy,
        wallClockNow, wallToReal,
    } = globalThis.BC;

    // Migration of older saved data (see loadChildren). Both can be removed after 2026-11-17, when the
    // last v1.x cookies (30-day lifetime) have expired.
    const STORAGE_KEY = 'birth'; // v2.0–2.5: a single child; moved into CHILDREN_KEY on first load
    const CHILDREN_KEY = 'children';
    const ACTIVE_CHILD_KEY = 'activeChild';
    const MODE_KEY = 'mode';
    const PREGNANCY_KEY = 'pregnancy';
    const LEGACY_COOKIE = 'datetime';

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
        // Each language page has its own <html lang>; anything else is treated as Croatian
        const pageLang = document.documentElement.lang;
        const lang = Object.prototype.hasOwnProperty.call(TEXT, pageLang) ? pageLang : 'hr';
        const t = texts(lang);

        // The chosen language is kept in a cookie; the server redirects "/" to "/en/", "/de/" or "/it/" accordingly.
        // Offline (page from the service worker cache) the page does the redirect itself.
        const savedLang = (document.cookie.match(/(?:^|; )lang=([a-z]{2})(?:;|$)/) || [])[1];
        if (lang === 'hr' && savedLang && savedLang !== 'hr' && Object.prototype.hasOwnProperty.call(TEXT, savedLang)) {
            location.replace(`/${savedLang}/${location.search}${location.hash}`);
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

        // Ask the browser to keep the saved data, so it isn't cleared when the device runs low on space. Asked at
        // most once per visit, and only while the visitor is doing something (not on page load): Firefox shows a
        // prompt, Chrome and Safari decide silently.
        let persistenceAsked = false;
        async function keepData() {
            if (persistenceAsked || !navigator.storage || !navigator.storage.persist) return;
            if (navigator.userActivation && !navigator.userActivation.isActive) return;
            persistenceAsked = true;
            try {
                if (!(await navigator.storage.persisted())) await navigator.storage.persist();
            } catch (e) { /* not supported or refused: the data is still saved, just not protected */ }
        }

        function saveChildren() {
            store(CHILDREN_KEY, children);
            store(ACTIVE_CHILD_KEY, activeId);
            keepData();
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

        const embryoDays = $('embryo-days');
        const gaWeeks = $('ga-weeks');
        const gaDays = $('ga-days');
        let lastBasis = 'due';

        function readPregnancyForm(basisValue = basis()) {
            const number = (input) => (input.value.trim() === '' ? NaN : Number(input.value));
            return {
                basis: basisValue, date: pregnancyDate.value, embryoDays: Number(embryoDays.value),
                gaWeeks: number(gaWeeks), gaDays: number(gaDays),
            };
        }

        function fillPregnancyForm(state) {
            basisInputs.forEach((input) => { input.checked = input.value === state.basis; });
            pregnancyDate.value = state.date;
            if (state.embryoDays) embryoDays.value = String(state.embryoDays);
            if (state.basis === 'ultrasound') {
                gaWeeks.value = String(state.gaWeeks);
                gaDays.value = String(state.gaDays);
            }
            updateBasis();
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
            loadCardIcon(); // ready before "Podijeli sliku" is pressed, so sharing stays within the user's gesture
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
            // With a valid date, only the ultrasound weeks and days can make the state invalid
            const state = validPregnancy(readPregnancyForm());
            if (!state) return showError(t.errors.gestationInvalid);
            const lmp = pregnancyLmp(state);
            const problem = pregnancyError(state.basis, lmp, wallClockNow(), lang, date);
            if (problem) return showError(problem);

            store(PREGNANCY_KEY, state);
            keepData();
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
            const chosen = basis();
            lastBasis = chosen;
            pregnancyDateLabel.textContent = t.dateLabel[chosen];
            $('ivf-fields').hidden = chosen !== 'ivf';
            $('ultrasound-fields').hidden = chosen !== 'ultrasound';
            gaWeeks.required = chosen === 'ultrasound';
            gaDays.required = chosen === 'ultrasound';
            // Dates that can give a pregnancy of 0 to 42 weeks today
            const [min, max] = {
                due: [today - 14 * DAY, today + PREGNANCY_DAYS * DAY],
                lmp: [today - 42 * 7 * DAY, today],
                ivf: [today - (42 * 7 - 14 - 3) * DAY, today],
                ultrasound: [today - 42 * 7 * DAY, today],
            }[chosen];
            pregnancyDate.min = isoDate(min);
            pregnancyDate.max = isoDate(max);
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
            // Keep the same pregnancy: describe what was entered with the newly chosen basis
            const previous = validPregnancy(readPregnancyForm(lastBasis));
            if (previous) {
                fillPregnancyForm(convertPregnancy(previous, basis(), wallClockNow()));
            } else {
                updateBasis();
            }
            if (pregnancyDate.value) calculatePregnancy();
        }));
        [embryoDays, gaWeeks, gaDays].forEach((input) => input.addEventListener('change', function () {
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
                const same = JSON.stringify(validPregnancy(local)) === JSON.stringify(backup.pregnancy);
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

        // --- Share picture (card.js) ---
        const pictureButton = $('share-picture');
        let cardIcon = null;

        function loadCardIcon() {
            if (!cardIcon) {
                const image = new Image();
                image.src = pictureButton.dataset.icon;
                cardIcon = image.decode().then(() => image).catch(() => null); // the card works without the icon
            }
            return cardIcon;
        }

        function cardContent() {
            const footer = location.host;
            if (current && current.mode === 'pregnancy') {
                return {
                    title: t.pregnancy, main: preg.duration.textContent,
                    lines: [preg.detail.textContent, `${t.dueDate}: ${preg.due.textContent}`], footer,
                };
            }
            const child = activeChild();
            const lines = [out.weeks.textContent];
            if (!corrected.card.hidden && /\d/.test(corrected.value.textContent)) {
                lines.push(`${t.corrected}: ${corrected.value.textContent}`);
            }
            lines.push(out.bornAt.textContent);
            return { title: child && child.name ? child.name : t.childAgeHeading, main: out.calendar.textContent, lines, footer };
        }

        function pictureName() {
            if (current && current.mode === 'pregnancy') {
                return `baby-calculator-pregnancy-${isoDate(current.lmp + PREGNANCY_DAYS * DAY)}.png`;
            }
            const child = activeChild();
            return `baby-calculator-${child ? child.date : todayValue()}.png`;
        }

        pictureButton.addEventListener('click', async function () {
            if (!current) return;
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const measure = (text, font) => {
                ctx.font = font;
                return ctx.measureText(text).width;
            };
            drawCard(canvas, layoutCard(cardContent(), measure), await loadCardIcon());
            const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
            if (!blob) {
                showStatus(t.pictureFailed);
                return;
            }
            const file = new File([blob], pictureName(), { type: 'image/png' });
            if (navigator.canShare && navigator.canShare({ files: [file] })) {
                try {
                    await navigator.share({ files: [file], title: 'Baby Calculator' });
                    return;
                } catch (e) {
                    if (e.name === 'AbortError') return;
                }
            }
            downloadFile(file.name, blob, 'image/png');
            showStatus(t.pictureSaved);
        });

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
            const savedPregnancy = validPregnancy(restore(PREGNANCY_KEY));
            if (savedPregnancy) fillPregnancyForm(savedPregnancy);
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
})();
