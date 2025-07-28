document.addEventListener('DOMContentLoaded', async () => {
    // グラフの共通設定
    const width = 400;
    const height = 400;
    const radius = Math.min(width, height) / 2;

    // 色のスケールを定義 (D3のカテゴリカルな色スキームを使用)
    const color = d3.scaleOrdinal(d3.schemeCategory10);

    // 円グラフのレイアウトを生成
    const pie = d3.pie()
        .value(d => d.value)
        .sort(null); // ソートしない

    // 円弧のジェネレーターを生成
    const arc = d3.arc()
        .innerRadius(0)
        .outerRadius(radius);

    try {
        // 統計データをAPIから取得
        const response = await fetch('/api/statistics');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const statistics = await response.json();
        console.log("DEBUG (statistics.js): 取得した統計データ:", statistics);

        // 各カテゴリの円グラフを描画
        drawPieChart(statistics.整備, '#seibi-pie-chart', '整備の種類別割合');
        drawPieChart(statistics.目的, '#purpose-pie-chart', '目的別割合');
        drawPieChart(statistics.発意, '#initiative-pie-chart', '発意別割合');
        drawPieChart(statistics.時期, '#period-pie-chart', '時期別割合');
        // 他のカテゴリも同様に追加

    } catch (error) {
        console.error('統計データの読み込み中にエラーが発生しました:', error);
        document.querySelectorAll('.chart-container').forEach(container => {
            container.innerHTML = `<p>統計データの読み込みに失敗しました。エラー: ${error.message}</p>`;
        });
    }

    // 円グラフを描画する共通関数
    function drawPieChart(data, containerSelector, titleText) {
        const container = d3.select(containerSelector);
        container.html(''); // 既存の「データ読み込み中...」をクリア

        if (!data || Object.keys(data).length === 0) {
            container.append('p').text('データがありません。');
            return;
        }

        // データをD3が扱える形式に変換
        const pieData = Object.entries(data).map(([key, value]) => ({ label: key, value: value }));

        const svg = container.append('svg')
            .attr('width', width)
            .attr('height', height)
            .append('g')
            .attr('transform', `translate(${width / 2},${height / 2})`);

        // 円グラフのパスを描画
        const arcs = svg.selectAll('.arc')
            .data(pie(pieData))
            .enter().append('g')
            .attr('class', 'arc');

        arcs.append('path')
            .attr('d', arc)
            .attr('fill', (d, i) => color(i));

        // ラベルを追加
        arcs.append('text')
            .attr('transform', d => `translate(${arc.centroid(d)})`)
            .attr('dy', '0.35em')
            .attr('text-anchor', 'middle')
            .text(d => d.data.label + ` (${d.data.value})`)
            .style('font-size', '12px')
            .style('fill', 'black'); // ラベルの色

        // タイトルを追加
        container.insert('h3', ':first-child') // グラフコンテナの先頭にタイトルを追加
            .text(titleText)
            .style('text-align', 'center')
            .style('color', '#2c3e50');
    }
});
