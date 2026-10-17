// Share picture on the page ("Podijeli sliku"): the card from card.js, shared as a file or downloaded.
// Page code (browser only), set up by app.js through BC.setupPicture.
(function (BC) {
    'use strict';

    const { DAY, drawCard, isoDate, layoutCard, PREGNANCY_DAYS, todayValue } = BC;

    // page: { t, current(), activeChild(), showStatus(message), downloadFile(name, content, type) }.
    // Returns loadCardIcon(), which app.js calls early so sharing stays within the user's gesture.
    BC.setupPicture = function (page) {
        const { t } = page;
        const $ = (id) => document.getElementById(id);
        const text = (id) => $(id).textContent;
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
            if (page.current() && page.current().mode === 'pregnancy') {
                return {
                    title: t.pregnancy, main: text('pregnancy-duration'),
                    lines: [text('pregnancy-detail'), `${t.dueDate}: ${text('pregnancy-due')}`], footer,
                };
            }
            const child = page.activeChild();
            const lines = [text('age-weeks')];
            if (!$('corrected-card').hidden && /\d/.test(text('corrected-value'))) {
                lines.push(`${t.corrected}: ${text('corrected-value')}`);
            }
            lines.push(text('born-at'));
            return { title: child && child.name ? child.name : t.childAgeHeading, main: text('age-calendar'), lines, footer };
        }

        function pictureName() {
            if (page.current() && page.current().mode === 'pregnancy') {
                return `baby-calculator-pregnancy-${isoDate(page.current().lmp + PREGNANCY_DAYS * DAY)}.png`;
            }
            const child = page.activeChild();
            return `baby-calculator-${child ? child.date : todayValue()}.png`;
        }

        pictureButton.addEventListener('click', async function () {
            if (!page.current()) return;
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const measure = (text, font) => {
                ctx.font = font;
                return ctx.measureText(text).width;
            };
            drawCard(canvas, layoutCard(cardContent(), measure), await loadCardIcon());
            const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
            if (!blob) {
                page.showStatus(t.pictureFailed);
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
            page.downloadFile(file.name, blob, 'image/png');
            page.showStatus(t.pictureSaved);
        });

        return { loadCardIcon };
    };
})(globalThis.BC = globalThis.BC || {});
