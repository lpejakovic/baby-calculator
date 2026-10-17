// Backup on the page: download, restore and transfer link, the backup reminder and the iPhone install hint.
// Page code (browser only), set up by app.js through BC.setupBackup; the backup format is in data.js.
(function (BC) {
    'use strict';

    const {
        BACKUP_MAX_BYTES, backupReminderDue, buildBackupLink, formatDate, makeBackup, mergeChildren, parseBackup,
        parseBirth, readBackupLink, todayValue, validPregnancy,
    } = BC;

    // For the reminder: the last backup, the last "Kasnije", and whether the iPhone hint was closed
    const LAST_BACKUP_KEY = 'lastBackup';
    const REMINDER_SNOOZED_KEY = 'backupReminderSnoozed';
    const IOS_HINT_CLOSED_KEY = 'iosHintClosed';

    // page: { t, lang, children, activeId (both settable), mode, activeChild(), saveChildren(), noteSaved(),
    //         store(key, value), restore(key), keys: { pregnancy, mode, firstSaved }, copy(text),
    //         downloadFile(name, content, type), showSaved() }.
    // Returns takeLink(), showMessage(message) and updateReminder().
    BC.setupBackup = function (page) {
        const { t, lang, store, restore, keys } = page;
        const $ = (id) => document.getElementById(id);
        const backupBox = $('backup');
        const backupStatus = $('backup-status');
        const backupFile = $('backup-file');

        function currentBackup() {
            return makeBackup({
                children: page.children, activeChild: page.activeId, pregnancy: restore(keys.pregnancy), mode: page.mode,
            }, new Date().toISOString());
        }

        // Merges a backup into the saved data and returns the message to show
        function applyBackup(backup) {
            const merged = mergeChildren(page.children, backup.children);
            page.children = merged.children;
            if (page.activeChild() === null && page.children.length) page.activeId = page.children[0].id;
            page.saveChildren();
            let pregnancyChanged = false;
            if (backup.pregnancy) {
                const local = restore(keys.pregnancy);
                const same = JSON.stringify(validPregnancy(local)) === JSON.stringify(backup.pregnancy);
                if (!same && (!local || !local.date || confirm(t.backupReplacePregnancy))) {
                    store(keys.pregnancy, backup.pregnancy);
                    pregnancyChanged = true;
                }
            }
            if (!merged.added && !merged.changed && !pregnancyChanged) return t.backupNothingNew;
            // Show what was restored
            store(keys.mode, merged.added || merged.changed || !pregnancyChanged ? 'baby' : 'pregnancy');
            return t.backupRestored;
        }

        $('backup-download').addEventListener('click', function () {
            page.downloadFile(`baby-calculator-${todayValue()}.json`, JSON.stringify(currentBackup(), null, 2),
                'application/json');
            markBackedUp();
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
            page.showSaved();
        });
        $('backup-link').addEventListener('click', async function () {
            const ok = await page.copy(buildBackupLink(location.origin + location.pathname, currentBackup()));
            backupStatus.textContent = ok ? t.backupLinkCopied : t.copyFailed;
            if (ok) markBackedUp();
        });

        // A transfer link (#backup=...) is merged once and then removed from the address bar
        function takeLink() {
            if (!/^#backup=/.test(location.hash)) return null;
            const linked = readBackupLink(location.hash);
            history.replaceState(null, '', location.pathname + location.search);
            return linked ? applyBackup(linked) : t.backupInvalid;
        }

        function showMessage(message) {
            if (!message) return;
            backupBox.open = true;
            backupStatus.textContent = message;
        }

        // --- Backup reminder and the iPhone install hint ---
        // The data lives only in this browser; Safari clears it after about a week without a visit, unless the
        // site was added to the Home Screen (where Safari offers no install prompt, so the page explains how).
        const reminder = $('backup-reminder');
        const iosHint = $('ios-install');
        const isIos = /iPad|iPhone|iPod/.test(navigator.userAgent)
            || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1); // iPadOS reports a Mac
        const standalone = navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches;

        function hasData() {
            return page.children.length > 0 || Boolean(validPregnancy(restore(keys.pregnancy)));
        }

        function updateReminder() {
            const today = todayValue();
            const last = restore(LAST_BACKUP_KEY);
            $('backup-last').textContent = last ? t.lastBackup(formatDate(parseBirth(last, ''), lang)) : t.lastBackupNever;
            if (hasData()) page.noteSaved(); // data saved before this version counts from today
            reminder.hidden = !backupReminderDue({
                hasData: hasData(), firstSaved: restore(keys.firstSaved), lastBackup: last,
                snoozed: restore(REMINDER_SNOOZED_KEY), today,
            });
            iosHint.hidden = !(isIos && !standalone && hasData() && !restore(IOS_HINT_CLOSED_KEY));
        }

        function markBackedUp() {
            store(LAST_BACKUP_KEY, todayValue());
            updateReminder();
        }

        $('reminder-backup').addEventListener('click', function () {
            $('backup-download').click();
            backupBox.querySelector('summary').focus();
        });
        $('reminder-later').addEventListener('click', function () {
            store(REMINDER_SNOOZED_KEY, todayValue());
            reminder.hidden = true;
            backupBox.querySelector('summary').focus();
        });
        $('ios-install-close').addEventListener('click', function () {
            store(IOS_HINT_CLOSED_KEY, true);
            iosHint.hidden = true;
        });

        return { takeLink, showMessage, updateReminder };
    };
})(globalThis.BC = globalThis.BC || {});
