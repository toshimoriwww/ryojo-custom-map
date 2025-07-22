document.addEventListener('DOMContentLoaded', async () => {
    // Extract category filter from the URL path
    const pathParts = window.location.pathname.split('/');
    let categoryFilter = null; 
    if (pathParts.length > 2 && pathParts[1] === 'cases') {
        const potentialCategory = pathParts[2];
        if (potentialCategory && potentialCategory !== 'all') { 
            categoryFilter = potentialCategory;
        }
    }
    
    console.log("DEBUG (cases_summary.js): URLから取得したカテゴリフィルター:", categoryFilter);

    const summaryCaseGridDiv = document.getElementById('summary-case-grid'); 

    try {
        // Fetch all case data from the Flask API
        const response = await fetch('/api/cases'); 
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const allCases = await response.json(); 

        console.log("DEBUG (cases_summary.js): APIから取得した全事例:", allCases);
        allCases.forEach(c => console.log(`  事例ID: ${c.id}, カテゴリ(フィルタ用): ${c.category}, カテゴリ(表示用): ${c.display_category_jp}`));


        // Filter cases based on the extracted category
        const filteredCases = categoryFilter
            ? allCases.filter(caseItem => {
                console.log(`  フィルタリング中: 事例ID: ${caseItem.id}, 事例カテゴリ: ${caseItem.category}, フィルター条件: ${categoryFilter}, 結果: ${caseItem.category === categoryFilter}`);
                return caseItem.category === categoryFilter; 
              })
            : allCases; 
        
        console.log("DEBUG (cases_summary.js): フィルタリング後の事例数:", filteredCases.length);


        summaryCaseGridDiv.innerHTML = ''; 

        if (filteredCases.length === 0) {
            summaryCaseGridDiv.innerHTML = '<p>表示する事例がありません。</p>';
            return;
        }

        // Render filtered cases as cards
        filteredCases.forEach(caseItem => {
            const caseDiv = document.createElement('div');
            caseDiv.className = 'summary-item'; 

            // app.pyから分離されたプロパティを直接使用
            const summaryAttributes = caseItem.summary_attributes_html || '<p>概要情報がありません。</p>'; 
            const statements = caseItem.statements_html || '<p>発言内容がありません。</p>'; 


            caseDiv.innerHTML = `
                <h3>${caseItem.name || '名称不明'}</h3> 
                ${caseItem.image_url ? `<img src="/static/images/${caseItem.image_url}" alt="事例 ${caseItem.id || ''}">` : ''} 
                
                ${summaryAttributes} 
                
                <div class="collapsible-statements">
                    <button class="toggle-statements-btn">ヒアリング内容を非表示</button> <!-- ★修正: 初期テキストを非表示に -->
                    <div class="statements-content" style="display: block;"> <!-- ★修正: display: block に変更 -->
                        <h4>ヒアリング内容:</h4> 
                        ${statements} 
                    </div>
                </div>

                <p><strong>カテゴリ:</strong> ${caseItem.display_category_jp || caseItem.category || '不明'}</p> 
            `;
            summaryCaseGridDiv.appendChild(caseDiv);

            // ヒアリング内容表示/非表示ボタンのイベントリスナーを設定
            const toggleButton = caseDiv.querySelector('.toggle-statements-btn');
            const statementsContent = caseDiv.querySelector('.statements-content');

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
        console.error('事例データの読み込み中にエラーが発生しました:', error);
        summaryCaseGridDiv.innerHTML = `<p>事例データの読み込みに失敗しました。エラー: ${error.message}</p>`;
    }
});
