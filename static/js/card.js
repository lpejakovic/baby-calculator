// Share card: a 1080×1080 picture of the age (or pregnancy), drawn in the browser.
// layoutCard() is pure (the tests run it in QuickJS with a stand-in text measure); drawCard() paints it on a canvas.
// Shared through the BC namespace; loaded before app.js (see templates/index.html).
(function (BC) {
    'use strict';

    const CARD_SIZE = 1080;
    const MARGIN = 96;          // text stays inside this margin
    const PANEL_INSET = 40;     // white panel on the light background
    const ICON_SIZE = 200;
    const COLORS = { background: '#f6f3fb', panel: '#ffffff', text: '#2b2838', primary: '#4f46b8', muted: '#6b6680' };
    const FONT_FAMILY = 'system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif';

    function cardFont(size, weight = 400) {
        return `${weight} ${size}px ${FONT_FAMILY}`;
    }

    // Shortens a line that is still too wide (e.g. one very long word) and ends it with "…"
    function clipLine(line, font, maxWidth, measure) {
        if (measure(line, font) <= maxWidth) return line;
        let clipped = line;
        while (clipped.length > 1 && measure(`${clipped}…`, font) > maxWidth) clipped = clipped.slice(0, -1);
        return `${clipped}…`;
    }

    // Greedy word wrap; measure(text, font) gives the width in pixels
    function wrapLines(text, font, maxWidth, measure) {
        const lines = [];
        let line = '';
        String(text).split(/\s+/).filter(Boolean).forEach((word) => {
            const candidate = line ? `${line} ${word}` : word;
            if (line && measure(candidate, font) > maxWidth) {
                lines.push(line);
                line = word;
            } else {
                line = candidate;
            }
        });
        if (line) lines.push(line);
        return lines;
    }

    // The largest of `sizes` at which the text fits in maxLines lines; otherwise the smallest, cut to maxLines
    function fitText(text, sizes, weight, maxWidth, maxLines, measure) {
        for (const size of sizes) {
            const font = cardFont(size, weight);
            const lines = wrapLines(text, font, maxWidth, measure);
            if (lines.length <= maxLines && lines.every((l) => measure(l, font) <= maxWidth)) return { size, lines };
        }
        const size = sizes[sizes.length - 1];
        const font = cardFont(size, weight);
        const lines = wrapLines(text, font, maxWidth, measure).slice(0, maxLines);
        return { size, lines: lines.map((l) => clipLine(l, font, maxWidth, measure)) };
    }

    const FOOTER_SIZE = 30;
    const FOOTER_Y = CARD_SIZE - MARGIN - FOOTER_SIZE;
    const SCALES = [1, 0.9, 0.8, 0.7, 0.6, 0.5];

    // The block above the footer at one scale (1 = full size); returns ops, icon and the bottom edge
    function layoutBlock(content, measure, scale) {
        const width = CARD_SIZE - 2 * MARGIN;
        const center = CARD_SIZE / 2;
        const px = (value) => Math.round(value * scale);
        const ops = [];
        const icon = { x: center - px(ICON_SIZE) / 2, y: MARGIN, size: px(ICON_SIZE) };
        let y = MARGIN + icon.size + px(48);

        const block = (text, sizes, weight, color, maxLines, gapAfter) => {
            const { size, lines } = fitText(text, sizes.map(px), weight, width, maxLines, measure);
            lines.forEach((line) => {
                ops.push({ text: line, x: center, y, size, font: cardFont(size, weight), color });
                y += Math.round(size * 1.2);
            });
            y += px(gapAfter);
        };
        block(content.title, [72, 64, 56, 48], 700, COLORS.text, 2, 24);
        block(content.main, [104, 96, 88, 80, 72, 64, 56], 700, COLORS.primary, 3, 32);
        content.lines.forEach((line) => block(line, [40, 36, 32], 400, COLORS.text, 2, 12));
        return { ops, icon, bottom: y };
    }

    // content: { title, main, lines: [...], footer }. Returns what to draw, top to bottom (textBaseline "top"):
    // the largest scale at which everything fits above the footer, centred in the space that is left.
    function layoutCard(content, measure) {
        const room = FOOTER_Y - 32;
        let block = null;
        for (const scale of SCALES) {
            block = layoutBlock(content, measure, scale);
            if (block.bottom <= room) break;
        }
        const shift = Math.max(0, Math.floor((room - block.bottom) / 2));
        const ops = block.ops.map((op) => ({ ...op, y: op.y + shift }));
        const footerFont = cardFont(FOOTER_SIZE, 400);
        ops.push({
            text: clipLine(content.footer, footerFont, CARD_SIZE - 2 * MARGIN, measure), x: CARD_SIZE / 2,
            y: FOOTER_Y, size: FOOTER_SIZE, font: footerFont, color: COLORS.muted, footer: true,
        });
        return { size: CARD_SIZE, icon: { ...block.icon, y: block.icon.y + shift }, ops };
    }

    function drawCard(canvas, layout, iconImage) {
        canvas.width = layout.size;
        canvas.height = layout.size;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = COLORS.background;
        ctx.fillRect(0, 0, layout.size, layout.size);
        ctx.fillStyle = COLORS.panel;
        const inner = layout.size - 2 * PANEL_INSET;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(PANEL_INSET, PANEL_INSET, inner, inner, 48);
        else ctx.rect(PANEL_INSET, PANEL_INSET, inner, inner);
        ctx.fill();
        if (iconImage) {
            ctx.save();
            ctx.beginPath();
            if (ctx.roundRect) ctx.roundRect(layout.icon.x, layout.icon.y, layout.icon.size, layout.icon.size, 40);
            else ctx.rect(layout.icon.x, layout.icon.y, layout.icon.size, layout.icon.size);
            ctx.clip();
            ctx.drawImage(iconImage, layout.icon.x, layout.icon.y, layout.icon.size, layout.icon.size);
            ctx.restore();
        }
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        layout.ops.forEach((op) => {
            ctx.font = op.font;
            ctx.fillStyle = op.color;
            ctx.fillText(op.text, op.x, op.y);
        });
    }

    Object.assign(BC, {
        CARD_SIZE, CARD_MARGIN: MARGIN, cardFont, clipLine, wrapLines, fitText, layoutCard, drawCard,
    });
})(globalThis.BC = globalThis.BC || {});
