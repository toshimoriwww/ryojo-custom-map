// Mapbox のアクセストークンを設定
mapboxgl.accessToken = 'pk.eyJ1IjoidG9zaGltb3JpIiwiYSI6ImNtZGJkOXl6ejB0MncyaW9mYXhlZmtmMjgifQ.QzkoNXEgQGc-BdzSAzwr8A'; // ★あなたのMapboxアクセストークンに置き換える！

document.addEventListener('DOMContentLoaded', () => {
    const caseForm = document.getElementById('caseForm');
    const formTitle = document.getElementById('form-title');
    const submitButton = document.getElementById('submitButton');
    const cancelEditButton = document.getElementById('cancelEditButton');
    const messageDiv = document.getElementById('message');
    const caseListAdmin = document.getElementById('case-list-admin');
    const currentCaseIdInput = document.getElementById('currentCaseId'); // hidden input for current case ID

    // フォームの入力要素をすべて取得
    const inputElements = Array.from(caseForm.elements).filter(el => el.tagName === 'INPUT' || el.tagName === 'TEXTAREA');

    // 管理画面用のMapbox地図を初期化
    const map = new mapboxgl.Map({
        container: 'admin-map', // admin.html内の地図コンテナID
        style: 'mapbox://styles/mapbox/streets-v12', // 管理画面ではシンプルな地図スタイル
        center: [132.55, 34.24], // 初期中心座標
        zoom: 12
    });

    // マーカーを保持するためのオブジェクト
    let currentMarkers = {}; 

    // 地図クリックで緯度経度をフォームに自動入力
    map.on('click', (e) => {
        document.getElementById('緯度').value = e.lngLat.lat.toFixed(6);
        document.getElementById('経度').value = e.lngLat.lng.toFixed(6);
        showMessage('info', '地図上の位置がフォームに自動入力されました。');
    });

    // 既存事例を読み込み、リストに表示
    async function loadAdminCases() {
        try {
            const response = await fetch('/api/cases'); // 全事例データを取得
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const cases = await response.json();

            caseListAdmin.innerHTML = ''; // リストをクリア
            // 既存のマーカーを地図から削除
            for (const id in currentMarkers) {
                if (currentMarkers[id]) { 
                    currentMarkers[id].remove();
                }
            }
            currentMarkers = {}; 

            if (cases.length === 0) {
                caseListAdmin.innerHTML = '<p>登録されている事例がありません。</p>';
                return;
            }

            cases.forEach(caseItem => {
                const li = document.createElement('li');
                li.innerHTML = `
                    <span>${caseItem.name}</span>
                    <button data-id="${caseItem.id}" class="edit-button">編集</button>
                    <button data-id="${caseItem.id}" class="delete-button">削除</button>
                `;
                caseListAdmin.appendChild(li);

                // マーカーを地図に追加（編集・削除の目印用）
                // 緯度経度が数値で有効な場合のみマーカーを作成
                const lat = caseItem.latitude;
                const lon = caseItem.longitude;
                const hasValidCoords = typeof lat === 'number' && !isNaN(lat) && typeof lon === 'number' && !isNaN(lon);

                if (hasValidCoords) {
                    const marker = new mapboxgl.Marker()
                        .setLngLat([lon, lat])
                        .addTo(map);
                    currentMarkers[caseItem.id] = marker; 
                } else {
                    console.warn(`事例 ${caseItem.id} (${caseItem.name}) に有効な緯度・経度がありません。地図上にマーカーは表示されません。`);
                }

                // 編集ボタンのイベントリスナー
                li.querySelector('.edit-button').addEventListener('click', () => editCase(caseItem.id));
                // 削除ボタンのイベントリスナー
                li.querySelector('.delete-button').addEventListener('click', () => confirmDelete(caseItem.id, caseItem.name));
            });

        } catch (error) {
            console.error('事例データの読み込み中にエラーが発生しました:', error);
            caseListAdmin.innerHTML = `<p>事例の読み込みに失敗しました。エラー: ${error.message}</p>`; 
        }
    }

    // 編集ボタンがクリックされた時の処理
    async function editCase(caseId) {
        formTitle.textContent = '事例の編集';
        submitButton.textContent = '事例を更新';
        cancelEditButton.style.display = 'inline-block'; 
        currentCaseIdInput.value = caseId; // 編集対象の事例IDを隠しフィールドに設定

        try {
            const response = await fetch(`/api/case/${caseId}`); // Flaskの単一事例取得APIにアクセス
            if (!response.ok) { 
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const caseData = await response.json(); // APIはオブジェクトを直接返す

            if (caseData) {
                // フォームにデータを自動入力
                inputElements.forEach(input => {
                    // input.name は HTMLフォームのinputの名前 (例: '事例', '発言内容', '写真')
                    // caseData は Flaskから取得したデータオブジェクト (例: {"事例": "R-01", "発言内容": "...", "写真": "..."})
                    if (caseData[input.name] !== undefined && caseData[input.name] !== null) { 
                        input.value = caseData[input.name];
                    } else {
                        input.value = ''; 
                    }
                });
                showMessage('info', `事例 ${caseId} の情報を編集しています。`);

                // 地図の中心を編集中の事例に移動 (緯度経度が有効な場合のみ)
                const lat = caseData['緯度'];
                const lon = caseData['経度'];
                if (typeof lat === 'number' && !isNaN(lat) && typeof lon === 'number' && !isNaN(lon)) {
                    map.flyTo({ center: [lon, lat], zoom: 15 });
                } else {
                    showMessage('warning', 'この事例には緯度・経度が設定されていません。地図で位置を指定してください。');
                }
            } else {
                showMessage('error', '事例データが見つかりませんでした。');
            }
        } catch (error) {
            console.error('事例データの取得中にエラー:', error);
            showMessage('error', `事例データの取得中にエラーが発生しました: ${error.message}`);
        }
    }

    // 編集キャンセルボタンの処理
    cancelEditButton.addEventListener('click', () => {
        resetForm();
        showMessage('info', '編集をキャンセルしました。');
    });

    // フォームリセット処理
    function resetForm() {
        caseForm.reset(); 
        formTitle.textContent = '新しい事例の追加';
        submitButton.textContent = '事例を追加';
        cancelEditButton.style.display = 'none';
        currentCaseIdInput.value = ''; 
    }

    // フォーム送信処理 (追加と更新を両方扱う)
    caseForm.addEventListener('submit', async (event) => {
        event.preventDefault(); 

        const formData = new FormData(caseForm);
        const data = {};
        formData.forEach((value, key) => {
            data[key] = value;
            if (key === '緯度' || key === '経度') {
                data[key] = parseFloat(value);
            }
        });

        const isEditing = currentCaseIdInput.value !== ''; 

        let url = '/api/cases/add';
        let successMessage = '事例が追加されました。';
        let errorMessage = '事例の追加中にエラーが発生しました。';

        if (isEditing) {
            url = '/api/cases/update'; 
            successMessage = '事例が更新されました。';
            errorMessage = '事例の更新中にエラーが発生しました。';
            data['事例'] = currentCaseIdInput.value; // 編集対象の事例IDをデータに追加
        }

        try {
            const response = await fetch(url, {
                method: 'POST', 
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                showMessage('success', result.message || successMessage);
                resetForm(); 
                loadAdminCases(); 

            } else {
                showMessage('error', result.message || errorMessage);
            }
        } catch (error) {
            console.error('API呼び出し中にエラーが発生しました:', error);
            showMessage('error', errorMessage);
        }
    });

    // メッセージ表示ヘルパー関数
    function showMessage(type, msg) {
        messageDiv.textContent = msg;
        messageDiv.className = `message-area ${type}`;
        setTimeout(() => {
            messageDiv.textContent = '';
            messageDiv.className = 'message-area';
        }, 5000); 
    }

    // 削除機能の実装 
    async function confirmDelete(caseId, caseName) {
        if (confirm(`本当に事例 ${caseName} (${caseId}) を削除しますか？`)) {
            try {
                const response = await fetch('/api/cases/delete', { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ '事例': caseId }) 
                });
                const result = await response.json();
                if (result.success) {
                    showMessage('success', result.message || '事例が削除されました。');
                    loadAdminCases();
                } else {
                    showMessage('error', result.message || '削除に失敗しました。');
                }
            } catch (error) {
                console.error('削除中にエラー:', error);
                showMessage('error', '削除中にネットワークエラーが発生しました。');
            }
        }
    }

    // ページロード時に事例を読み込む
    loadAdminCases();
});