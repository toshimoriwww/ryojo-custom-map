// ★あなたのMapboxアクセストークンに置き換えてください！
mapboxgl.accessToken = 'pk.eyJ1IjoidG9zaGltb3JpIiwiYSI6ImNtZGJkOXl6ejB0MncyaW9mYXhlZmtmMjgifQ.QzkoNXEgQGc-BdzSAzwr8A'; 

const map = new mapboxgl.Map({
    container: 'map', 
    style: 'mapbox://styles/mapbox/satellite-streets-v12', // 航空写真スタイル
    center: [132.55, 34.24], 
    zoom: 15, 
    pitch: 45, 
    bearing: -17.6, 
    antialias: true
});

// --- 地形表示の追加 (スタイルがロードされたら実行) ---
map.on('style.load', () => {
    map.addSource('mapbox-dem', {
        'type': 'raster-dem',
        'url': 'mapbox://mapbox.mapbox-terrain-dem-v1',
        'tileSize': 512,
        'maxzoom': 14 
    });
    map.setTerrain({ 'source': 'mapbox-dem', 'exaggeration': 2 }); 

    map.addLayer({
        'id': 'sky',
        'type': 'sky',
        'paint': {
            'sky-type': 'atmosphere',
            'sky-atmosphere-sun': [0.0, 0.0],
            'sky-atmosphere-sun-intensity': 15
        }
    });
});

// 地図の最初のロードが完了したら実行される処理
map.on('load', async () => {
    // --- 3D建物の追加 ---
    const layers = map.getStyle().layers;
    let labelLayerId;
    for (let i = 0; i < layers.length; i++) {
        if (layers[i].type === 'symbol' && layers[i].layout['text-field']) {
            labelLayerId = layers[i].id;
            break;
        }
    }

    if (!map.getLayer('3d-buildings')) {
        map.addLayer(
            {
                'id': '3d-buildings',
                'source': 'composite', 
                'source-layer': 'building',
                'filter': ['==', 'extrude', 'true'],
                'type': 'fill-extrusion',
                'minzoom': 15,
                'paint': {
                    'fill-extrusion-color': '#aaa',
                    'fill-extrusion-height': [
                        'interpolate',
                        ['linear'],
                        ['zoom'],
                        15,
                        0,
                        15.05,
                        ['get', 'height']
                    ],
                    'fill-extrusion-base': [
                        'interpolate',
                        ['linear'],
                        ['zoom'],
                        15,
                        0,
                        15.05,
                        ['get', 'min_height']
                    ],
                    'fill-extrusion-opacity': 0.6
                }
            },
            labelLayerId
        );
    }
    
    await loadCases(); 
});

// データベースから事例データを取得し、地図とサイドバーに表示する関数
async function loadCases() {
    try {
        console.log('APIからデータを取得しようとしています...'); 
        const response = await fetch('/api/cases'); 
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const cases = await response.json(); 
        console.log('取得したデータ (グループ化後):', cases); 

        const caseListDiv = document.getElementById('case-list'); 
        if (!caseListDiv) {
            console.error("エラー: ID 'case-list' の要素が見つかりません。index.html を確認してください。");
            return; 
        }
        caseListDiv.innerHTML = ''; 

        if (cases.length === 0) {
            caseListDiv.innerHTML = '<p>表示する事例がありません。</p>';
            return;
        }

        // ★修正: 重複座標を追跡するためのMapをループの外で初期化
        const placedCoordinates = new Map(); // Map<"lat,lon", count>

        cases.forEach(point => {
            let lat = point.latitude;
            let lon = point.longitude;
            const hasValidCoords = typeof lat === 'number' && !isNaN(lat) && typeof lon === 'number' && !isNaN(lon);

            if (hasValidCoords) {
                const coordKey = `${lat.toFixed(6)},${lon.toFixed(6)}`; // 緯度経度を文字列キーに変換
                let offsetCount = placedCoordinates.get(coordKey) || 0;

                if (offsetCount > 0) {
                    // ★修正: シンプルな線形オフセットを適用 (右にずらす)
                    const offsetAmount = 0.0001; // オフセット量 (度数)。小さい値で試す
                    lon += offsetAmount * offsetCount; // 経度を増やすことで右にずれる
                    console.log(`DEBUG: Applying offset to ${point.name}. Original: ${point.longitude}, New: ${lon.toFixed(6)}`);
                }
                placedCoordinates.set(coordKey, offsetCount + 1); // カウントを増やす

                const markerColor = point.is_area_wide ? '#FFD700' : '#007cbf'; 

                const el = document.createElement('div');
                el.className = 'custom-marker';
                if (point.is_area_wide) {
                    el.classList.add('area-wide'); 
                }
                el.style.backgroundColor = markerColor; 
                
                el.textContent = point.name || `事例 ${point.id}`; 

                marker = new mapboxgl.Marker(el)
                    .setLngLat([lon, lat]) 
                    .addTo(map);
            } else {
                console.warn(`事例 ${point.id} (${point.name}) に有効な緯度・経度がありません。地図上にマーカーは表示されません。`);
            }

            // ポップアップの内容を作成
            let popupContent = `<h3>${point.name || '名称不明'}</h3>`; 
            if (point.image_url) { 
                popupContent += `<img src="/static/images/${point.image_url}" alt="事例 ${point.id || ''}" style="max-width:100%; margin-bottom: 10px;">`;
            }
            popupContent += point.description; 

            const popup = new mapboxgl.Popup({ offset: 25 })
                .setHTML(popupContent);
            
            if (marker) {
                marker.setPopup(popup);
            }

            // サイドバーに事例リスト項目を追加
            const caseItem = document.createElement('div');
            caseItem.className = 'case-item';
            caseItem.innerHTML = `
                <h3>${point.name || '名称不明'}</h3> 
                ${point.image_url ? `<img src="/static/images/${point.image_url}" alt="事例 ${point.id || ''}">` : ''} 
                ${point.description} 
            `;
            caseItem.onclick = () => {
                const originalLat = point.latitude;
                const originalLon = point.longitude;
                if (typeof originalLat === 'number' && !isNaN(originalLat) && typeof originalLon === 'number' && !isNaN(originalLon)) {
                    map.flyTo({ center: [originalLon, originalLat], zoom: 15, pitch: 45 });
                    if (marker) { 
                        marker.getPopup().addTo(map);
                    }
                } else {
                    showMessage('info', `事例 ${point.name} には地図上の位置情報がありません。`);
                }
            };
            caseListDiv.appendChild(caseItem);
        });

    } catch (error) {
        console.error('データの読み込み中にエラーが発生しました:', error);
        document.getElementById('case-list').innerHTML = '<p>データの読み込みに失敗しました。サーバーが起動しているか確認してください。</p>';
    }
}

// メッセージ表示ヘルパー関数（script.jsにも追加）
function showMessage(type, msg) {
    const messageArea = document.getElementById('message-area-main-map'); 
    if (!messageArea) {
        console.warn('Message area not found on main map page.');
        alert(msg); 
        return;
    }
    messageArea.textContent = msg;
    messageArea.className = `message-area ${type}`;
    setTimeout(() => {
        messageArea.textContent = '';
        messageArea.className = 'message-area';
    }, 5000); 
}

// (オプション) 地図をクリックした場所の緯度経度をコンソールに表示
map.on('click', function(e) {
    console.log("クリックした場所: ", e.lngLat.lat.toFixed(6), ", ", e.lngLat.lng.toFixed(6));
});
