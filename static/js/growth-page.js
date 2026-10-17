// Growth section of the page: the measurements table, the WHO chart and the form to add a measurement.
// Page code (browser only), set up by app.js through BC.setupGrowth; the calculations are in growth.js.
(function (BC) {
    'use strict';

    const {
        ageInMonths, chartMonths, formatDate, formatPercentile, GROWTH_LYING_MONTHS, growthChart, MEASURES,
        measurePercentile, parseBirth, startOfDay, todayValue, wallClockNow, WHO_GROWTH,
    } = BC;
    const UNITS = { weight: 'kg', length: 'cm', head: 'cm' };
    const SVG = 'http://www.w3.org/2000/svg';

    // page: { t, lang, activeChild(), updateActiveChild(changes), snapshot(), offerUndo(message, before),
    //         babyShown() }. Returns render() and reset(child).
    BC.setupGrowth = function (page) {
        const { t, lang } = page;
        const $ = (id) => document.getElementById(id);
        const growth = {
            box: $('growth'), form: $('measure-form'), date: $('measure-date'), error: $('measure-error'),
            chart: $('growth-chart'), list: $('measurements'), listBox: $('measurements-box'),
            corrected: $('growth-corrected'), add: $('measure-add'),
        };
        const measureInputs = { weight: $('measure-weight'), length: $('measure-length'), head: $('measure-head') };
        const sexInputs = document.querySelectorAll('input[name="sex"]');
        const measureTabs = document.querySelectorAll('input[name="measure"]');

        function chosenMeasure() {
            return document.querySelector('input[name="measure"]:checked').value;
        }

        // Age on the WHO curves at a date: for a baby born early the corrected age (from the due date), as is usual
        // up to 2 years of actual age; otherwise, and after that, the actual age
        function growthAge(child, dateMs) {
            const birth = startOfDay(parseBirth(child.date, ''));
            const due = child.due ? parseBirth(child.due, '') : null;
            const actual = ageInMonths(birth, dateMs);
            return due !== null && due > birth && actual < GROWTH_LYING_MONTHS ? ageInMonths(due, dateMs) : actual;
        }

        function bornEarly(child) {
            return Boolean(child.due) && parseBirth(child.due, '') > parseBirth(child.date, '');
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
        function percentileText(table, child, date, value) {
            const months = growthAge(child, parseBirth(date, ''));
            if (months < 0) return t.beforeTerm;
            const p = measurePercentile(table, months, value);
            return p === null ? t.after60 : formatPercentile(p);
        }

        function renderGrowth() {
            const child = page.activeChild();
            if (!child) return;
            sexInputs.forEach((input) => { input.checked = input.value === child.sex; });
            growth.date.min = child.date;
            growth.date.max = todayValue();
            if (!growth.date.value) growth.date.value = todayValue();
            const tables = child.sex ? WHO_GROWTH[child.sex === 'f' ? 'girls' : 'boys'] : null;
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
                        p.textContent = percentileText(tables[key], child, m.date, m[key]);
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
                    const before = page.snapshot();
                    page.updateActiveChild({ measurements: measurements.filter((other) => other.date !== m.date) });
                    renderGrowth();
                    page.offerUndo(t.measurementRemoved(when), before);
                });
                const removeCell = document.createElement('td');
                removeCell.append(remove);
                row.append(removeCell);
                return row;
            }));
            // Nothing measured yet: the form is all there is to do, so it is open
            if (!measurements.length) growth.add.open = true;

            growth.corrected.hidden = !(tables && bornEarly(child));
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
                .map((m) => ({ months: growthAge(child, parseBirth(m.date, '')), value: m[measure] }));
            const months = chartMonths(ageInMonths(startOfDay(parseBirth(child.date, '')), wallClockNow()), points);
            // Drawn at the real width, so the text keeps its size on phones (a closed section has no width yet)
            const width = Math.max(280, Math.round(growth.chart.clientWidth || 600));
            const height = Math.round(Math.min(360, Math.max(240, width * 0.62)));
            const model = growthChart(tables[measure], points, width, height, months);
            growth.chart.replaceChildren(chartSvg(model, t.growthChartLabel(t.measures[measure])));
        }

        function showMeasureError(message) {
            growth.error.textContent = message;
            growth.error.hidden = false;
        }

        growth.form.addEventListener('submit', function (event) {
            event.preventDefault();
            const child = page.activeChild();
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
            page.updateActiveChild({ measurements: [...(child.measurements || []), entry] });
            Object.values(measureInputs).forEach((input) => { input.value = ''; });
            growth.error.hidden = true;
            renderGrowth();
        });
        sexInputs.forEach((input) => input.addEventListener('change', function () {
            page.updateActiveChild({ sex: input.value });
            renderGrowth();
        }));
        measureTabs.forEach((input) => input.addEventListener('change', renderGrowth));
        growth.box.addEventListener('toggle', () => growth.box.open && renderGrowth());
        let resizeFrame = null;
        window.addEventListener('resize', function () {
            cancelAnimationFrame(resizeFrame);
            resizeFrame = requestAnimationFrame(() => growth.box.open && page.babyShown() && renderGrowth());
        });

        // Closed again (open when the child has measurements) for another child or on load
        function reset(child) {
            growth.box.open = Boolean(child && child.measurements);
            growth.add.open = false;
            growth.date.value = '';
        }

        return { render: renderGrowth, reset };
    };
})(globalThis.BC = globalThis.BC || {});
