document.addEventListener('DOMContentLoaded', async () => {
    const customizeCaseGridDiv = document.getElementById('customize-case-grid');
    const historicalTimelineContainer = document.getElementById('historical-timeline-container'); // 年表コンテナ

    try {
        // ★新規追加: 歴史年表データを取得し描画
        await loadHistoricalSummary();

        // カスタマイズされた事例データをAPIから取得
        const response = await fetch('/api/customize_cases');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const customizeCases = await response.json();
        console.log("DEBUG (customize.js): 取得したカスタマイズ事例:", customizeCases);

        customizeCaseGridDiv.innerHTML = '';

        if (customizeCases.length === 0) {
            customizeCaseGridDiv.innerHTML = '<p>表示するカスタマイズ事例がありません。</p>';
            return;
        }

        // 発意と所有でグループ化するためのMap
        const groupedByInitiativeAndOwnership = new Map(); // Map<"発意_所有", [caseItem1, caseItem2]>

        customizeCases.forEach(caseItem => {
            // app.pyから渡された initiative_for_card と ownership_for_card を使用
            const initiative = caseItem.initiative_for_card || '不明';
            const ownership = caseItem.ownership_for_card || '不明';
            const groupKey = `${initiative}_${ownership}`; // 例: "個人_公道", "自治会_私有地"

            if (!groupedByInitiativeAndOwnership.has(groupKey)) {
                groupedByInitiativeAndOwnership.set(groupKey, []);
            }
            groupedByInitiativeAndOwnership.get(groupKey).push(caseItem);
        });

        // グループごとにレンダリング
        groupedByInitiativeAndOwnership.forEach((casesInGroup, groupKey) => {
            const [initiative, ownership] = groupKey.split('_');

            const groupSection = document.createElement('section');
            groupSection.className = 'customize-group-section';
            
            // グループ見出し
            groupSection.innerHTML = `<h2>発意: ${initiative} / 所有: ${ownership}</h2>`;
            
            const groupGrid = document.createElement('div');
            groupGrid.className = 'customize-group-grid'; // 新しいグリッドクラス

            casesInGroup.forEach(caseItem => {
                const caseDiv = document.createElement('div');
                caseDiv.className = 'summary-item'; 

                // 発意に応じてCSSクラスを追加して色分け
                let initiativeClass = '';
                if (initiative === '個人') {
                    initiativeClass = 'initiative-individual';
                } else if (initiative === '自治会') {
                    initiativeClass = 'initiative-jichikai';
                }
                // 他の発意タイプがあればここに追加
                if (initiativeClass) {
                    caseDiv.classList.add(initiativeClass);
                }
                // 所有に応じてさらに色分けやスタイルを追加することも可能 (例: ownership-public, ownership-private)
                // if (ownership === '公道') { caseDiv.classList.add('ownership-public'); }

                const summaryAttributes = caseItem.summary_attributes_html || '<p>概要情報がありません。</p>';
                const statements = caseItem.statements_html || '<p>発言内容がありません。</p>';
                const speakersList = caseItem.speakers_list_html || ''; // 発言者リスト

                caseDiv.innerHTML = `
                    <h3>${caseItem.name || '名称不明'}</h3> <!-- 事例名（Excelの「事例名」列）をタイトルとして表示 -->
                    ${caseItem.image_url ? `<img src="/static/images/${caseItem.image_url}" alt="事例 ${caseItem.id || ''}">` : ''} <!-- 写真を優先表示 -->
                    
                    ${summaryAttributes} <!-- 概要部分（整備以外の要素）を直接挿入 -->
                    
                    <div class="collapsible-statements">
                        <button class="toggle-statements-btn">ヒアリング内容を表示</button> <!-- 初期テキストは「表示」 -->
                        <div class="statements-content" style="display: none;"> <!-- 初期状態では非表示 -->
                            <h4>ヒアリング内容:</h4>
                            ${statements} <!-- 実際の発言内容と詳細要素 -->
                            ${speakersList ? `<p><strong>発言者:</strong> ${speakersList}</p>` : ''} <!-- 発言者リスト -->
                        </div>
                    </div>

                    <p><strong>カテゴリ:</strong> ${caseItem.display_category_jp || caseItem.category || '不明'}</p>
                `;
                groupGrid.appendChild(caseDiv); // グループのグリッドにカードを追加
            });
            groupSection.appendChild(groupGrid); // グループセクションにグリッドを追加
            customizeCaseGridDiv.appendChild(groupSection); // メインのコンテナにグループセクションを追加
        });

        // ヒアリング内容表示/非表示ボタンのイベントリスナーを再設定
        customizeCaseGridDiv.querySelectorAll('.toggle-statements-btn').forEach(toggleButton => {
            const statementsContent = toggleButton.nextElementSibling; // ボタンの次の要素が内容
            if (toggleButton && statementsContent) {
                toggleButton.addEventListener('click', () => {
                    if (statementsContent.style.display === 'none') {
                        statementsContent.style.display = 'block';
                        toggleButton.textContent = 'ヒアリング内容を非表示';
                    } else {
                        statementsContent.style.display = 'none';
                        toggleButton.textContent = 'ヒアリング内容を表示';
                    }
                });
            }
        });


    } catch (error) {
        console.error('カスタマイズ事例データの読み込み中にエラーが発生しました:', error);
        customizeCaseGridDiv.innerHTML = `<p>カスタマイズ事例データの読み込みに失敗しました。エラー: ${error.message}</p>`;
    }

    // ★新規追加: 歴史年表データを読み込み、表示する関数
    async function loadHistoricalSummary() {
        try {
            const response = await fetch('/api/historical_summary');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const historicalData = await response.json();
            console.log("DEBUG (customize.js): 取得した歴史年表データ:", historicalData);

            historicalTimelineContainer.innerHTML = ''; // コンテナをクリア

            if (Object.keys(historicalData).length === 0) {
                historicalTimelineContainer.innerHTML = '<p>歴史データがありません。</p>';
                return;
            }

            // 時期でソートされたキーを取得
            const sortedPeriods = Object.keys(historicalData).sort((a, b) => {
                // 簡易的なソートロジック。より複雑な時期表現にはカスタムソート関数が必要
                // 例: '昭和40年代' < '昭和52年' < '平成' < '最近'
                const order = {
                    '戦前': 0, '昭和初期': 1, '昭和20年代': 2, '昭和30年代': 3, '昭和40年代': 4,
                    '昭和50年代': 5, '昭和52年': 5.1, '昭和60年代': 6, '昭和64年': 6.1, '平成初期': 7,
                    '10～20年前': 10, '10年前': 11, '20年前': 9, '25~30年前': 8, '最近': 12, '1年前': 13,'不明な時期': 99
                };
                const valA = order[a] !== undefined ? order[a] : parseFloat(a) || 98; // 数値変換できないものは最後に
                const valB = order[b] !== undefined ? order[b] : parseFloat(b) || 98;
                return valA - valB;
            });


            const timelineList = document.createElement('div');
            timelineList.className = 'timeline-list'; // 新しいスタイルクラス

            sortedPeriods.forEach(period => {
                const timelineItem = document.createElement('div');
                timelineItem.className = 'timeline-item';

                const timelineYear = document.createElement('div');
                timelineYear.className = 'timeline-year';
                timelineYear.textContent = period;
                timelineItem.appendChild(timelineYear);

                const timelineContent = document.createElement('div');
                timelineContent.className = 'timeline-content';
                const ul = document.createElement('ul');
                
                historicalData[period].forEach(seibi => {
                    const li = document.createElement('li');
                    li.textContent = seibi;
                    ul.appendChild(li);
                });
                timelineContent.appendChild(ul);
                timelineItem.appendChild(timelineContent);

                timelineList.appendChild(timelineItem);
            });
            historicalTimelineContainer.appendChild(timelineList);

        } catch (error) {
            console.error('歴史年表データの読み込み中にエラーが発生しました:', error);
            historicalTimelineContainer.innerHTML = `<p>歴史年表データの読み込みに失敗しました。エラー: ${error.message}</p>`;
        }
    }
});
