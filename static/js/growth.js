// Growth: WHO percentiles from the LMS data in who-growth.js (birth to 24 months) and the chart geometry.
// Pure: no DOM or storage. Shared through the BC namespace; loaded before app.js (see templates/index.html).
(function (BC) {
    'use strict';

    const { DAY, startOfDay } = BC;

    const DAYS_PER_MONTH = 365.25 / 12; // WHO's month: 30.4375 days
    const MAX_MONTHS = 24;
    // Accepted measurements (anything outside is a typo, e.g. grams instead of kilograms)
    const MEASURES = {
        weight: { min: 0.3, max: 30, decimals: 2 },
        length: { min: 25, max: 120, decimals: 1 },
        head: { min: 15, max: 60, decimals: 1 },
    };
    // Lines on the chart, with their z-scores
    const PERCENTILE_LINES = [[3, -1.880794], [15, -1.036433], [50, 0], [85, 1.036433], [97, 1.880794]];

    // Age in months on the WHO scale, by date only
    function ageInMonths(startMs, dateMs) {
        return (startOfDay(dateMs) - startOfDay(startMs)) / DAY / DAYS_PER_MONTH;
    }

    // L, M and S at an age in months, interpolated between completed months; null outside 0–24 months
    function lmsAt(table, months) {
        if (!(months >= 0 && months <= MAX_MONTHS)) return null;
        const i = Math.min(Math.floor(months), MAX_MONTHS - 1);
        const f = months - i;
        return [0, 1, 2].map((k) => table[i][k] + (table[i + 1][k] - table[i][k]) * f);
    }

    function zScore(value, [L, M, S]) {
        return L === 0 ? Math.log(value / M) / S : ((value / M) ** L - 1) / (L * S);
    }

    function valueAt([L, M, S], z) {
        return L === 0 ? M * Math.exp(S * z) : M * (1 + L * S * z) ** (1 / L);
    }

    // Standard normal distribution (Abramowitz & Stegun 7.1.26; error below 1.5e-7)
    function normalCdf(z) {
        const x = Math.abs(z) / Math.SQRT2;
        const t = 1 / (1 + 0.3275911 * x);
        const erf = 1 - t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))))
            * Math.exp(-x * x);
        return z >= 0 ? (1 + erf) / 2 : (1 - erf) / 2;
    }

    function percentileOf(z) {
        return normalCdf(z) * 100;
    }

    // "P50", "P2.5", "<P0.1", ">P99.9"
    function formatPercentile(p) {
        if (p < 0.1) return '<P0.1';
        if (p > 99.9) return '>P99.9';
        const rounded = p < 1 || p > 99 ? Math.round(p * 10) / 10 : Math.round(p);
        return `P${rounded}`;
    }

    // Percentile of one measured value, or null when the age is outside 0–24 months
    function measurePercentile(table, months, value) {
        const lms = lmsAt(table, months);
        return lms ? percentileOf(zScore(value, lms)) : null;
    }

    // Chart geometry in a width × height box: the percentile curves as SVG paths, the child's points, axis ticks.
    // points: [{ months, value }] (outside 0–24 months they are left out)
    function growthChart(table, points, width, height) {
        const pad = { left: 44, right: 40, top: 12, bottom: 30 };
        const ages = [];
        for (let m = 0; m <= MAX_MONTHS; m += 0.25) ages.push(m);
        const shown = points.filter((p) => p.months >= 0 && p.months <= MAX_MONTHS);
        const low = Math.min(...ages.map((m) => valueAt(lmsAt(table, m), PERCENTILE_LINES[0][1])), ...shown.map((p) => p.value));
        const high = Math.max(...ages.map((m) => valueAt(lmsAt(table, m), PERCENTILE_LINES[4][1])), ...shown.map((p) => p.value));
        const step = niceStep((high - low) / 6);
        const yMin = Math.floor(low / step) * step;
        const yMax = Math.ceil(high / step) * step;
        const x = (months) => pad.left + (months / MAX_MONTHS) * (width - pad.left - pad.right);
        const y = (value) => height - pad.bottom - ((value - yMin) / (yMax - yMin)) * (height - pad.top - pad.bottom);
        const round = (n) => Math.round(n * 10) / 10;

        const curves = PERCENTILE_LINES.map(([p, z]) => {
            const coords = ages.map((m) => [round(x(m)), round(y(valueAt(lmsAt(table, m), z)))]);
            return {
                percentile: p,
                d: coords.map(([cx, cy], i) => `${i ? 'L' : 'M'}${cx} ${cy}`).join(' '),
                labelX: coords[coords.length - 1][0] + 4,
                labelY: coords[coords.length - 1][1],
            };
        });
        const yTicks = [];
        for (let v = yMin; v <= yMax + step / 2; v += step) yTicks.push({ value: round(v), y: round(y(v)) });
        const xTicks = [0, 3, 6, 9, 12, 15, 18, 21, 24].map((m) => ({ months: m, x: round(x(m)) }));
        return {
            width, height, pad, curves, yTicks, xTicks,
            points: shown.map((p) => ({ ...p, x: round(x(p.months)), y: round(y(p.value)) })),
        };
    }

    // 1, 2 or 5 × a power of ten
    function niceStep(raw) {
        const power = 10 ** Math.floor(Math.log10(raw));
        const n = raw / power;
        return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * power;
    }

    // Measurements as stored with a child: [{ date, weight?, length?, head? }], sorted by date, one per date
    function cleanMeasurements(list) {
        if (!Array.isArray(list)) return [];
        const byDate = new Map();
        list.forEach((m) => {
            if (!m || typeof m.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(m.date)) return;
            const entry = { date: m.date };
            Object.keys(MEASURES).forEach((key) => {
                const value = m[key];
                const range = MEASURES[key];
                if (typeof value === 'number' && value >= range.min && value <= range.max) entry[key] = value;
            });
            if (Object.keys(entry).length > 1) byDate.set(m.date, { ...byDate.get(m.date), ...entry });
        });
        return [...byDate.values()].sort((a, b) => (a.date < b.date ? -1 : 1)).slice(-200);
    }

    Object.assign(BC, {
        DAYS_PER_MONTH, GROWTH_MAX_MONTHS: MAX_MONTHS, MEASURES, PERCENTILE_LINES, ageInMonths, lmsAt, zScore,
        valueAt, normalCdf, percentileOf, formatPercentile, measurePercentile, growthChart, niceStep, cleanMeasurements,
    });
})(globalThis.BC = globalThis.BC || {});
