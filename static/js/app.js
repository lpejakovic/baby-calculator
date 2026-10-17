// Page code: forms, results, storage and events. The pure logic is in texts.js, dates.js,
// calendar.js and data.js, loaded before this file.
(function () {
    'use strict';

    const {
        addSharedChild, ageInMonths, babyCalendarEvents, backupReminderDue, BACKUP_MAX_BYTES, buildBackupLink, buildIcs,
        buildShareUrl, calculateAge, childLabel, cleanChild, convertPregnancy, correctedAge, correctedAgeError,
        countdown, DAY, drawCard, dueCountdown, formatBirth, formatDate, formatPercentile, growthChart, isoDate,
        joinClock, joinParts, layoutCard, makeBackup, measurePercentile, MEASURES, mergeChildren, nextChildId,
        normalizeChildren, parseBackup, parseBirth, PREGNANCY_DAYS, pregnancyCalendarEvents, pregnancyError,
        pregnancyLmp, pregnancyMilestones, pregnancyStatus, readBackupLink, readSharedBirth, readSharedPregnancy,
        removeChild, startOfDay, TEXT, texts, todayValue, upcomingMilestones, validPregnancy, wallClockNow,
        wallToReal, WHO_GROWTH,
    } = globalThis.BC;

    const CHILDREN_KEY = 'children';
    const ACTIVE_CHILD_KEY = 'activeChild';
    const MODE_KEY = 'mode';
    const PREGNANCY_KEY = 'pregnancy';
    // For the backup reminder: when something was first saved, the last backup, the last "Kasnije"
    const FIRST_SAVED_KEY = 'firstSaved';
    const LAST_BACKUP_KEY = 'lastBackup';
    const REMINDER_SNOOZED_KEY = 'backupReminderSnoozed';
    const IOS_HINT_CLOSED_KEY = 'iosHintClosed';

    function loadChildren() {
        return normalizeChildren(restore(CHILDREN_KEY));
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
        const intro = $('intro');
        const editButton = $('edit-entry');
        const formFields = [$('birth-fields'), $('pregnancy-fields')];
        const shareToggle = $('share-toggle');
        const shareMenu = $('share-menu');
        const shareButton = $('share-link');
        const copyButton = $('copy-text');
        const shareStatus = $('share-status');
        const undo = { bar: $('undo'), text: $('undo-text'), button: $('undo-button') };
        let undoState = null; // the children just before a removal, while "Poništi" is offered
        let undoTimer = null;
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

        function noteSaved() {
            if (!restore(FIRST_SAVED_KEY)) store(FIRST_SAVED_KEY, todayValue());
        }

        function saveChildren() {
            hideUndo(); // anything saved after a removal replaces what "Poništi" would bring back
            store(CHILDREN_KEY, children);
            store(ACTIVE_CHILD_KEY, activeId);
            if (children.length) noteSaved();
            keepData();
        }

        // After removing a child or a measurement (already saved): "Poništi" brings back the list as it was before
        function offerUndo(message, before) {
            undoState = before;
            undo.text.textContent = message;
            undo.button.textContent = t.undo;
            undo.bar.hidden = false;
            announce.textContent = message;
            undo.button.focus();
            const close = () => {
                // Not while the visitor is on the button
                if (undo.bar.contains(document.activeElement)) undoTimer = setTimeout(close, 2000);
                else hideUndo();
            };
            clearTimeout(undoTimer);
            undoTimer = setTimeout(close, 10000);
        }

        function hideUndo() {
            undoState = null;
            clearTimeout(undoTimer);
            undo.bar.hidden = true;
        }

        undo.button.addEventListener('click', function () {
            const before = undoState;
            if (!before) return;
            children = before.children;
            activeId = before.activeId;
            saveChildren();
            selectChild(activeId);
            if (!result.hidden) result.focus();
        });

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
            growth.box.open = Boolean(child && child.measurements);
            growth.add.open = false;
            growth.date.value = '';
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

        // While a result is shown the form is folded away behind "Uredi podatke", so the result comes first
        function setEditing(on) {
            formFields.forEach((fields) => { fields.hidden = !on; });
            editButton.hidden = on;
        }

        // After "Izračunaj": the result is scrolled to and gets the focus, so it is read out next
        function focusResult(section) {
            section.focus({ preventScroll: true });
            const top = section.getBoundingClientRect().top;
            if (top >= 0 && top < innerHeight / 2) return; // already in view
            const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            section.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' });
        }

        function hideResults() {
            setEditing(true);
            setShareMenu(false);
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
            intro.hidden = true; // only for the first visit, before anything is calculated
            updateBackupReminder(); // e.g. the iPhone hint, right after the first save
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
            out.total.textContent = joinClock([[age.elapsedDays, 'day'], [age.hours, 'hour'],
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

        // how: 'show' (folds the form away), 'submit' (also moves to the result) or 'live' (while editing)
        function calculate(how = 'show') {
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
            renderGrowth();
            if (how !== 'live') setEditing(false);
            if (how === 'submit') focusResult(result);
            announce.textContent = `${named || t.age}: ${out.calendar.textContent}, ${t.or} ${out.weeks.textContent}.`;

            clearInterval(timer);
            timer = setInterval(() => render(birth, due), 1000);
        }

        function calculatePregnancy(how = 'show') {
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
            noteSaved();
            keepData();
            show(pregnancyResult);

            current = { mode: 'pregnancy', lmp };
            milestonesDay = null;
            renderPregnancy(lmp);
            if (how !== 'live') setEditing(false);
            if (how === 'submit') focusResult(pregnancyResult);
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

        // "Podijeli" opens a short list: link, text or picture
        function setShareMenu(open) {
            shareMenu.hidden = !open;
            shareToggle.setAttribute('aria-expanded', String(open));
        }
        shareToggle.addEventListener('click', () => setShareMenu(shareMenu.hidden));
        shareMenu.addEventListener('keydown', function (event) {
            if (event.key !== 'Escape') return;
            setShareMenu(false);
            shareToggle.focus();
        });

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
            calculate('submit');
        });
        dateInput.addEventListener('change', () => dateInput.value && calculate('live'));
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
            const before = { children, activeId };
            const next = removeChild(children, child.id);
            children = next.children;
            saveChildren();
            selectChild(next.activeId);
            offerUndo(t.childRemoved(childLabel(child, before.children.indexOf(child), lang)), before);
        });
        timeInput.addEventListener('change', () => dateInput.value && calculate('live'));
        dueInput.addEventListener('change', () => dateInput.value && calculate('live'));

        pregnancyForm.addEventListener('submit', function (event) {
            event.preventDefault();
            calculatePregnancy('submit');
        });
        pregnancyDate.addEventListener('change', () => pregnancyDate.value && calculatePregnancy('live'));
        basisInputs.forEach((input) => input.addEventListener('change', function () {
            // Keep the same pregnancy: describe what was entered with the newly chosen basis
            const previous = validPregnancy(readPregnancyForm(lastBasis));
            if (previous) {
                fillPregnancyForm(convertPregnancy(previous, basis(), wallClockNow()));
            } else {
                updateBasis();
            }
            if (pregnancyDate.value) calculatePregnancy('live');
        }));
        [embryoDays, gaWeeks, gaDays].forEach((input) => input.addEventListener('change', function () {
            if (pregnancyDate.value) calculatePregnancy('live');
        }));
        editButton.addEventListener('click', function () {
            setEditing(true);
            (mode === 'baby' ? nameInput : document.querySelector('input[name="basis"]:checked')).focus();
        });
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

        // --- Growth (growth.js, who-growth.js) ---
        const growth = {
            box: $('growth'), form: $('measure-form'), date: $('measure-date'), error: $('measure-error'),
            chart: $('growth-chart'), list: $('measurements'), listBox: $('measurements-box'),
            corrected: $('growth-corrected'), add: $('measure-add'),
        };
        const measureInputs = { weight: $('measure-weight'), length: $('measure-length'), head: $('measure-head') };
        const sexInputs = document.querySelectorAll('input[name="sex"]');
        const measureTabs = document.querySelectorAll('input[name="measure"]');
        const UNITS = { weight: 'kg', length: 'cm', head: 'cm' };
        const SVG = 'http://www.w3.org/2000/svg';

        function chosenMeasure() {
            return document.querySelector('input[name="measure"]:checked').value;
        }

        function updateActiveChild(changes) {
            children = children.map((c) => (c.id === activeId ? cleanChild({ ...c, ...changes }) : c));
            saveChildren();
        }

        // Age 0 on the WHO curves: the birth, or the due date for a baby born early (corrected age)
        function growthStart(child) {
            const birth = parseBirth(child.date, '');
            const due = child.due ? parseBirth(child.due, '') : null;
            return due !== null && due > birth ? { start: due, corrected: true } : { start: startOfDay(birth), corrected: false };
        }

        function formatNumber(value) {
            return new Intl.NumberFormat(lang, { maximumFractionDigits: 2 }).format(value);
        }

        function svg(name, attributes, text) {
            const element = document.createElementNS(SVG, name);
            Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
            if (text !== undefined) element.textContent = text;
            return element;
        }

        function chartSvg(model, label) {
            const root = svg('svg', {
                viewBox: `0 0 ${model.width} ${model.height}`, width: model.width, height: model.height,
                role: 'img', 'aria-label': label,
            });
            const left = model.pad.left;
            const right = model.width - model.pad.right;
            const bottom = model.height - model.pad.bottom;
            model.yTicks.forEach((tick) => {
                root.append(svg('line', { class: 'grid', x1: left, x2: right, y1: tick.y, y2: tick.y }));
                root.append(svg('text', { class: 'axis', x: left - 6, y: tick.y + 4, 'text-anchor': 'end' }, formatNumber(tick.value)));
            });
            model.xTicks.forEach((tick) => {
                root.append(svg('text', { class: 'axis', x: tick.x, y: bottom + 18, 'text-anchor': 'middle' }, String(tick.months)));
            });
            root.append(svg('text', { class: 'axis', x: right, y: model.height - 2, 'text-anchor': 'end' }, t.axisMonths));
            model.curves.forEach((curve) => {
                root.append(svg('path', { class: `curve curve-${curve.percentile}`, d: curve.d }));
                root.append(svg('text', { class: 'axis', x: curve.labelX, y: curve.labelY + 4 }, `P${curve.percentile}`));
            });
            if (model.points.length > 1) {
                const d = model.points.map((p, i) => `${i ? 'L' : 'M'}${p.x} ${p.y}`).join(' ');
                root.append(svg('path', { class: 'child-line', d }));
            }
            model.points.forEach((p) => root.append(svg('circle', { class: 'point', cx: p.x, cy: p.y, r: 5 })));
            return root;
        }

        // "P50", or why there is no percentile
        function percentileText(table, start, date, value) {
            const months = ageInMonths(start, parseBirth(date, ''));
            if (months < 0) return t.beforeTerm;
            const p = measurePercentile(table, months, value);
            return p === null ? t.after24 : formatPercentile(p);
        }

        function renderGrowth() {
            const child = activeChild();
            if (!child) return;
            sexInputs.forEach((input) => { input.checked = input.value === child.sex; });
            growth.date.min = child.date;
            growth.date.max = todayValue();
            if (!growth.date.value) growth.date.value = todayValue();
            const tables = child.sex ? WHO_GROWTH[child.sex === 'f' ? 'girls' : 'boys'] : null;
            const { start, corrected } = growthStart(child);
            const measurements = child.measurements || [];

            // Newest first: date, then each value with its percentile under it
            growth.listBox.hidden = measurements.length === 0;
            growth.list.replaceChildren(...[...measurements].reverse().map((m) => {
                const row = document.createElement('tr');
                const when = formatDate(parseBirth(m.date, ''), lang);
                const date = document.createElement('th');
                date.scope = 'row';
                date.textContent = when;
                row.append(date, ...Object.keys(UNITS).map((key) => {
                    const cell = document.createElement('td');
                    if (m[key] === undefined) return cell;
                    cell.textContent = formatNumber(m[key]);
                    if (tables) {
                        const p = document.createElement('span');
                        p.className = 'percentile';
                        p.textContent = percentileText(tables[key], start, m.date, m[key]);
                        cell.append(p);
                    }
                    return cell;
                }));
                const remove = document.createElement('button');
                remove.type = 'button';
                remove.className = 'button-link';
                remove.textContent = '×';
                remove.setAttribute('aria-label', t.removeMeasurement(when));
                remove.addEventListener('click', () => {
                    const before = { children, activeId };
                    updateActiveChild({ measurements: measurements.filter((other) => other.date !== m.date) });
                    renderGrowth();
                    offerUndo(t.measurementRemoved(when), before);
                });
                const removeCell = document.createElement('td');
                removeCell.append(remove);
                row.append(removeCell);
                return row;
            }));
            // Nothing measured yet: the form is all there is to do, so it is open
            if (!measurements.length) growth.add.open = true;

            growth.corrected.hidden = !(tables && corrected);
            growth.corrected.textContent = t.correctedNote;
            if (!tables) {
                const hint = document.createElement('p');
                hint.className = 'hint';
                hint.textContent = t.sexMissing;
                growth.chart.replaceChildren(hint);
                return;
            }
            const measure = chosenMeasure();
            const points = measurements.filter((m) => m[measure] !== undefined)
                .map((m) => ({ months: ageInMonths(start, parseBirth(m.date, '')), value: m[measure] }));
            // Drawn at the real width, so the text keeps its size on phones (a closed section has no width yet)
            const width = Math.max(280, Math.round(growth.chart.clientWidth || 600));
            const height = Math.round(Math.min(360, Math.max(240, width * 0.62)));
            const model = growthChart(tables[measure], points, width, height);
            growth.chart.replaceChildren(chartSvg(model, t.growthChartLabel(t.measures[measure])));
        }

        function showMeasureError(message) {
            growth.error.textContent = message;
            growth.error.hidden = false;
        }

        growth.form.addEventListener('submit', function (event) {
            event.preventDefault();
            const child = activeChild();
            if (!child) return;
            const date = parseBirth(growth.date.value, '');
            if (date === null || date < startOfDay(parseBirth(child.date, '')) || date > parseBirth(todayValue(), '')) {
                showMeasureError(t.measureDate);
                return;
            }
            const entry = { date: growth.date.value };
            for (const [key, input] of Object.entries(measureInputs)) {
                const raw = input.value.trim().replace(',', '.');
                if (!raw) continue;
                const value = Number(raw);
                const range = MEASURES[key];
                if (!(value >= range.min && value <= range.max)) {
                    showMeasureError(t.measureRange(t.measures[key], formatNumber(range.min), formatNumber(range.max), UNITS[key]));
                    input.focus();
                    return;
                }
                entry[key] = value;
            }
            if (Object.keys(entry).length === 1) {
                showMeasureError(t.measureNoValue);
                return;
            }
            // A second measurement on the same date adds to it (new values win)
            updateActiveChild({ measurements: [...(child.measurements || []), entry] });
            Object.values(measureInputs).forEach((input) => { input.value = ''; });
            growth.error.hidden = true;
            renderGrowth();
        });
        sexInputs.forEach((input) => input.addEventListener('change', function () {
            updateActiveChild({ sex: input.value });
            renderGrowth();
        }));
        measureTabs.forEach((input) => input.addEventListener('change', renderGrowth));
        growth.box.addEventListener('toggle', () => growth.box.open && renderGrowth());
        let resizeFrame = null;
        window.addEventListener('resize', function () {
            cancelAnimationFrame(resizeFrame);
            resizeFrame = requestAnimationFrame(() => growth.box.open && current && current.mode === 'baby' && renderGrowth());
        });

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
            markBackedUp();
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
            if (ok) markBackedUp();
        });

        // A transfer link (#backup=...) is merged once and then removed from the address bar
        function takeBackupLink() {
            if (!/^#backup=/.test(location.hash)) return null;
            const linked = readBackupLink(location.hash);
            history.replaceState(null, '', location.pathname + location.search);
            return linked ? applyBackup(linked) : t.backupInvalid;
        }
        const backupMessage = takeBackupLink();

        // --- Backup reminder and the iPhone install hint ---
        // The data lives only in this browser; Safari clears it after about a week without a visit, unless the
        // site was added to the Home Screen (where Safari offers no install prompt, so the page explains how).
        const reminder = $('backup-reminder');
        const iosHint = $('ios-install');
        const isIos = /iPad|iPhone|iPod/.test(navigator.userAgent)
            || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1); // iPadOS reports a Mac
        const standalone = navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches;

        function hasData() {
            return children.length > 0 || Boolean(validPregnancy(restore(PREGNANCY_KEY)));
        }

        function updateBackupReminder() {
            const today = todayValue();
            const last = restore(LAST_BACKUP_KEY);
            $('backup-last').textContent = last ? t.lastBackup(formatDate(parseBirth(last, ''), lang)) : t.lastBackupNever;
            if (hasData()) noteSaved(); // data saved before this version counts from today
            reminder.hidden = !backupReminderDue({
                hasData: hasData(), firstSaved: restore(FIRST_SAVED_KEY), lastBackup: last,
                snoozed: restore(REMINDER_SNOOZED_KEY), today,
            });
            iosHint.hidden = !(isIos && !standalone && hasData() && !restore(IOS_HINT_CLOSED_KEY));
        }

        function markBackedUp() {
            store(LAST_BACKUP_KEY, todayValue());
            updateBackupReminder();
        }

        $('reminder-backup').addEventListener('click', function () {
            $('backup-download').click();
            $('backup').querySelector('summary').focus();
        });
        $('reminder-later').addEventListener('click', function () {
            store(REMINDER_SNOOZED_KEY, todayValue());
            reminder.hidden = true;
            $('backup').querySelector('summary').focus();
        });
        $('ios-install-close').addEventListener('click', function () {
            store(IOS_HINT_CLOSED_KEY, true);
            iosHint.hidden = true;
        });

        // Fills the forms from the saved data and shows the saved mode
        function showSaved() {
            const child = activeChild();
            nameInput.value = child ? child.name : '';
            dateInput.value = child ? child.date : '';
            timeInput.value = child ? child.time : '';
            dueInput.value = child ? child.due : '';
            premature.open = Boolean(dueInput.value);
            growth.box.open = Boolean(child && child.measurements);
            growth.add.open = false;
            store(ACTIVE_CHILD_KEY, activeId);
            renderChildren();
            const savedPregnancy = validPregnancy(restore(PREGNANCY_KEY));
            if (savedPregnancy) fillPregnancyForm(savedPregnancy);
            intro.hidden = Boolean(children.length || savedPregnancy);
            refreshDateLimits();
            setMode(restore(MODE_KEY) === 'pregnancy' ? 'pregnancy' : 'baby');
            updateBackupReminder();
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
