(function () {
    'use strict';

    const canvas = document.getElementById('latency-evolution-chart');
    const payloadElement = document.getElementById('latency-series-data');
    const emptyState = document.getElementById('latency-chart-empty');
    const detail = document.getElementById('latency-chart-detail');
    if (!canvas || !payloadElement) return;

    const data = JSON.parse(payloadElement.textContent || '{}');
    const labels = data.labels || [];
    const average = data.average || [];
    const p95 = data.p95 || [];
    const counts = data.counts || [];
    const queries = data.queries || [];
    const hasData = queries.length > 0 || average.some(value => value !== null);

    if (!hasData) {
        canvas.hidden = true;
        emptyState.hidden = false;
        return;
    }

    const context = canvas.getContext('2d');
    const palette = {
        grid: '#30363d',
        text: '#8b949e',
        average: '#58a6ff',
        averageFill: 'rgba(88, 166, 255, .12)',
        p95: '#d29922',
        query: '#3fb950',
        surface: '#161b22'
    };
    let points = [];

    function formatMs(value) {
        if (value === null || value === undefined) return 'Sin datos';
        if (value >= 1000) return `${(value / 1000).toFixed(1)} s`;
        return `${Math.round(value)} ms`;
    }

    function draw() {
        const ratio = window.devicePixelRatio || 1;
        const width = canvas.clientWidth;
        const height = canvas.clientHeight;
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
        context.clearRect(0, 0, width, height);

        const padding = {top: 18, right: 18, bottom: 38, left: 58};
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;
        const values = [
            ...average,
            ...p95,
            ...queries.map(item => item.latency)
        ].filter(value => value !== null);
        const maximum = Math.max(...values, 1);
        const yMaximum = Math.ceil(maximum / 10000) * 10000 || maximum;
        const x = index => padding.left + (
            labels.length <= 1 ? chartWidth / 2 : index * chartWidth / (labels.length - 1)
        );
        const y = value => padding.top + chartHeight - (value / yMaximum) * chartHeight;

        context.font = '11px Inter, sans-serif';
        context.textBaseline = 'middle';
        for (let step = 0; step <= 4; step += 1) {
            const value = yMaximum * step / 4;
            const py = padding.top + chartHeight - chartHeight * step / 4;
            context.strokeStyle = palette.grid;
            context.lineWidth = 1;
            context.beginPath();
            context.moveTo(padding.left, py);
            context.lineTo(width - padding.right, py);
            context.stroke();
            context.fillStyle = palette.text;
            context.textAlign = 'right';
            context.fillText(formatMs(value), padding.left - 9, py);
        }

        const labelStep = Math.max(1, Math.ceil(labels.length / 7));
        labels.forEach((label, index) => {
            if (index % labelStep !== 0 && index !== labels.length - 1) return;
            context.fillStyle = palette.text;
            context.textAlign = 'center';
            context.fillText(label, x(index), height - 15);
        });

        function drawSeries(valuesToDraw, color, fill) {
            const validPoints = valuesToDraw.map((value, index) => (
                value === null ? null : {x: x(index), y: y(value), value, index}
            ));
            context.strokeStyle = color;
            context.lineWidth = 2;
            context.beginPath();
            let drawing = false;
            validPoints.forEach(point => {
                if (!point) {
                    drawing = false;
                    return;
                }
                if (!drawing) context.moveTo(point.x, point.y);
                else context.lineTo(point.x, point.y);
                drawing = true;
            });
            context.stroke();

            if (fill) {
                const available = validPoints.filter(Boolean);
                if (available.length > 1) {
                    context.save();
                    context.globalAlpha = 1;
                    context.fillStyle = fill;
                    context.beginPath();
                    context.moveTo(available[0].x, padding.top + chartHeight);
                    available.forEach(point => context.lineTo(point.x, point.y));
                    context.lineTo(available[available.length - 1].x, padding.top + chartHeight);
                    context.closePath();
                    context.fill();
                    context.restore();
                }
            }
            return validPoints;
        }

        const averagePoints = drawSeries(average, palette.average, palette.averageFill);
        const p95Points = drawSeries(p95, palette.p95);
        const queryX = index => padding.left + (
            queries.length <= 1
                ? chartWidth / 2
                : index * chartWidth / (queries.length - 1)
        );
        const queryPoints = queries.map((item, index) => ({
            index,
            label: item.label,
            x: queryX(index),
            y: y(item.latency),
            value: item.latency,
            type: 'query'
        }));
        if (queryPoints.length) {
            context.strokeStyle = palette.query;
            context.lineWidth = 1.5;
            context.globalAlpha = 0.82;
            context.beginPath();
            queryPoints.forEach((point, index) => {
                if (index === 0) context.moveTo(point.x, point.y);
                else context.lineTo(point.x, point.y);
            });
            context.stroke();
            queryPoints.forEach(point => {
                context.beginPath();
                context.arc(point.x, point.y, 2.5, 0, Math.PI * 2);
                context.fillStyle = palette.query;
                context.fill();
            });
            context.globalAlpha = 1;
        }
        points = labels.map((label, index) => ({
            index,
            label,
            x: x(index),
            average: averagePoints[index],
            p95: p95Points[index],
            count: counts[index] || 0
        })).concat(queryPoints);
    }

    canvas.addEventListener('mousemove', event => {
        const rect = canvas.getBoundingClientRect();
        const mouseX = event.clientX - rect.left;
        const candidates = points.filter(
            point => point.type === 'query' || point.average || point.p95
        );
        if (!candidates.length) return;
        const closest = candidates.reduce((best, point) => (
            Math.abs(point.x - mouseX) < Math.abs(best.x - mouseX) ? point : best
        ));
        if (closest.type === 'query') {
            detail.textContent = `${closest.label} · Consulta ${formatMs(closest.value)}`;
        } else {
            detail.textContent = `${closest.label} · Promedio ${formatMs(average[closest.index])} · P95 ${formatMs(p95[closest.index])} · ${closest.count} trazas`;
        }
    });
    canvas.addEventListener('mouseleave', () => {
        detail.textContent = 'Pasa el cursor por la gráfica para ver el detalle';
    });

    const resizeObserver = new ResizeObserver(draw);
    resizeObserver.observe(canvas);
    draw();
}());
