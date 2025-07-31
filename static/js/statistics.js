document.addEventListener('DOMContentLoaded', async () => {
    try {
        // 統計データをAPIから取得 (app.pyでフィルタリング済み)
        const response = await fetch('/api/statistics');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const statistics = await response.json();
        console.log("DEBUG (statistics.js): 取得した統計データ:", statistics);

        // 各カテゴリの統計データをリスト形式で描画
        renderStatisticsList(statistics.整備, '#seibi-pie-chart', '整備の種類別割合 (個人・自治会発意)');
        renderStatisticsList(statistics.目的, '#purpose-pie-chart', '目的別割合 (個人・自治会発意)');
        renderStatisticsList(statistics.発意, '#initiative-pie-chart', '発意別割合 (個人・自治会発意)');
        renderStatisticsList(statistics.時期, '#period-pie-chart', '時期別割合 (個人・自治会発意)');
        // 他のカテゴリも同様に追加

    } catch (error) {
        console.error('統計データの読み込み中にエラーが発生しました:', error);
        document.querySelectorAll('.chart-container').forEach(container => {
            container.innerHTML = `<p>統計データの読み込みに失敗しました。エラー: ${error.message}</p>`;
        });
    }

    // ★新規追加: 統計データをリスト形式で描画する共通関数
    function renderStatisticsList(data, containerSelector, titleText) {
        const container = document.querySelector(containerSelector);
        if (!container) {
            console.error(`Container not found for selector: ${containerSelector}`);
            return;
        }
        container.innerHTML = ''; // 既存の「データ読み込み中...」をクリア

        const h3Title = document.createElement('h3');
        h3Title.textContent = titleText;
        container.appendChild(h3Title);

        if (!data || Object.keys(data).length === 0) {
            container.innerHTML += '<p>データがありません。</p>';
            return;
        }

        const ul = document.createElement('ul');
        ul.className = 'statistics-list'; // 新しいCSSクラス

        // データをカウントが多い順にソート
        const sortedData = Object.entries(data).sort(([,a],[,b]) => b - a);

        sortedData.forEach(([label, value]) => {
            const li = document.createElement('li');
            li.className = 'statistics-list-item'; // 新しいCSSクラス
            li.innerHTML = `<strong>${label}</strong>: ${value} 件`;
            ul.appendChild(li);
        });
        container.appendChild(ul);
    }
});
