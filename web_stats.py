from flask import Flask, render_template_string, jsonify
from collections import Counter
import json
from pathlib import Path
import datetime
import requests
import time
from datetime import timedelta
import os

app = Flask(__name__)
app.static_folder = 'static'

# 确保static目录存在
os.makedirs('static', exist_ok=True)
#请添加自己的MAP API
BING_API_KEY = ""

# 预定义主要城市的坐标
KNOWN_LOCATIONS = {
    "Moscow": {"lat": 55.7558, "lon": 37.6173, "country": "Russia", "admin_area": "Moscow"},
    "Beijing": {"lat": 39.9042, "lon": 116.4074, "country": "China", "admin_area": "Beijing"},
    "Shanghai": {"lat": 31.2304, "lon": 121.4737, "country": "China", "admin_area": "Shanghai"},
    "Hong Kong": {"lat": 22.3193, "lon": 114.1694, "country": "China", "admin_area": "Hong Kong"},
    "Singapore": {"lat": 1.3521, "lon": 103.8198, "country": "Singapore", "admin_area": "Singapore"},
    "Tokyo": {"lat": 35.6762, "lon": 139.6503, "country": "Japan", "admin_area": "Tokyo"},
    "London": {"lat": 51.5074, "lon": -0.1278, "country": "United Kingdom", "admin_area": "London"},
    "New York": {"lat": 40.7128, "lon": -74.0060, "country": "United States", "admin_area": "New York"},
    "Paris": {"lat": 48.8566, "lon": 2.3522, "country": "France", "admin_area": "Île-de-France"},
    "Guangzhou": {"lat": 23.1291, "lon": 113.2644, "country": "China", "admin_area": "Guangdong"},
    "Shenzhen": {"lat": 22.5429, "lon": 114.0596, "country": "China", "admin_area": "Guangdong"},
    "Seoul": {"lat": 37.5665, "lon": 126.9780, "country": "South Korea", "admin_area": "Seoul"},
}

# 国家信息映射
COUNTRY_INFO = {
    "Moscow": "Russia",
    "Beijing": "China",
    "Shanghai": "China",
    "Guangzhou": "China",
    "Shenzhen": "China",
    "Hong Kong": "China",
    "Singapore": "Singapore",
    "Tokyo": "Japan",
    "Seoul": "South Korea",
    "Hanoi": "Vietnam",
    "Bangkok": "Thailand",
    "London": "United Kingdom",
    "Paris": "France",
    "New York": "United States"
}

class GeoData:
    def __init__(self):
        self.geo_file = Path('geo_data.json')
        self.geo_data = self._load_geo_data()
        self.verify_cache()

    def _load_geo_data(self):
        """加载缓存的地理位置数据"""
        if self.geo_file.exists():
            try:
                with open(self.geo_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("Invalid JSON in geo_data.json, creating new file")
                return {}
        return {}

    def verify_cache(self):
        """验证缓存数据的准确性"""
        verified_data = {}
        for city, location in self.geo_data.items():
            if self._verify_location(city, location):
                verified_data[city] = location
            else:
                print(f"Removing invalid cache entry for {city}")
        self.geo_data = verified_data
        self._save_geo_data()
        
    def _verify_location(self, city, location):
        """验证位置数据的准确性"""
        if city in KNOWN_LOCATIONS:
            known = KNOWN_LOCATIONS[city]
            return abs(location['lat'] - known['lat']) < 1 and abs(location['lon'] - known['lon']) < 1
            
        if city in COUNTRY_INFO:
            return location.get('country', '') == COUNTRY_INFO[city]
            
        return True
        
    def _save_geo_data(self):
        """保存地理位置数据到文件"""
        try:
            with open(self.geo_file, 'w', encoding='utf-8') as f:
                json.dump(self.geo_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving geo data: {e}")
            
    def get_city_location(self, city):
        """获取城市的地理位置"""
        if city in KNOWN_LOCATIONS:
            print(f"Using predefined location for {city}")
            return KNOWN_LOCATIONS[city]
            
        if city in self.geo_data:
            print(f"Using cached data for {city}")
            return self.geo_data[city]
            
        try:
            print(f"Fetching location for {city} from Bing Maps API")
            url = f"http://dev.virtualearth.net/REST/v1/Locations"
            
            params = {
                'query': city,
                'key': BING_API_KEY,
                'maxResults': 5,
                'culture': 'zh-CN',
                'includeNeighborhood': 1,
                'include': 'queryParse'
            }
            
            if city in COUNTRY_INFO:
                params['query'] = f"{city}, {COUNTRY_INFO[city]}"
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                if data['statusCode'] == 200 and data['resourceSets'] and data['resourceSets'][0]['resources']:
                    for resource in data['resourceSets'][0]['resources']:
                        location = resource['point']['coordinates']
                        country = resource.get('address', {}).get('countryRegion', '')
                        admin_area = resource.get('address', {}).get('adminDistrict', '')
                        
                        if city in COUNTRY_INFO and country != COUNTRY_INFO[city]:
                            continue
                            
                        result = {
                            'lat': location[0],
                            'lon': location[1],
                            'country': country,
                            'admin_area': admin_area,
                            'last_updated': datetime.datetime.now().isoformat()
                        }
                        
                        if self._verify_location(city, result):
                            self.geo_data[city] = result
                            self._save_geo_data()
                            print(f"Successfully found and cached location for {city}: {result}")
                            return result
                    
            print(f"Could not find valid location for {city}")
            return None
            
        except Exception as e:
            print(f"Error getting location for {city}: {e}")
            return None

def load_attempts():
    """加载SSH尝试记录"""
    try:
        with open('ssh_attempts.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def get_stats():
    """获取统计数据"""
    attempts = load_attempts()
    
    # 基础统计
    ip_counts = Counter()
    city_counts = Counter()
    hourly_counts = Counter()
    now = datetime.datetime.now()
    twenty_four_hours_ago = now - timedelta(hours=24)
    
    # IP-城市映射
    ip_city_map = {}
    
    for attempt in attempts:
        ip = attempt['ip']
        city = attempt.get('city', 'Unknown')
        ip_city_map[ip] = city
        
        try:
            timestamp = datetime.datetime.fromisoformat(attempt['timestamp'])
            if timestamp >= twenty_four_hours_ago:
                hour = timestamp.strftime('%H:00')
                hourly_counts[hour] += 1
        except:
            pass
            
        ip_counts[ip] += 1
        city_counts[city] += 1

    # 获取前10的IP和城市
    top_ips = [(ip, ip_city_map[ip], count) for ip, count in ip_counts.most_common(10)]
    top_cities = city_counts.most_common(10)
    
    # 24小时趋势数据
    hours = []
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    for i in range(24):
        hour = current_hour - timedelta(hours=i)
        hour_str = hour.strftime('%H:00')
        hours.append({
            'hour': hour_str,
            'count': hourly_counts.get(hour_str, 0)
        })
    hours.reverse()

    return {
        'top_ips': top_ips,
        'top_cities': top_cities,
        'hourly_trend': hours,
        'total_attempts': len(attempts),
        'unique_ips': len(ip_counts),
        'unique_cities': len(city_counts)
    }

@app.route('/api/map_data')
def map_data():
    """提供地图数据API"""
    geo = GeoData()
    attempts = load_attempts()
    
    city_counts = Counter()
    for attempt in attempts:
        city = attempt.get('city', 'Unknown')
        if city != 'Unknown':
            city_counts[city] += 1
    
    map_points = []
    for city, count in city_counts.items():
        location = geo.get_city_location(city)
        if location:
            point_data = {
                'city': city,
                'count': count,
                'lat': location['lat'],
                'lon': location['lon']
            }
            if 'country' in location:
                point_data['country'] = location['country']
            if 'admin_area' in location:
                point_data['admin_area'] = location['admin_area']
            map_points.append(point_data)
    
    return jsonify(map_points)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>是谁在敲打我窗</title>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="30">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f0f2f5;
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding: 0 20px;
        }
        .refresh-btn {
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .refresh-btn:hover {
            background-color: #45a049;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 20px;
            padding: 0 20px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }
        .stat-number {
            font-size: 24px;
            font-weight: bold;
            color: #4CAF50;
        }
        .container {
            display: flex;
            gap: 20px;
            margin-top: 20px;
            padding: 0 20px;
        }
        .column {
            flex: 1;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .rank-list {
            list-style-type: none;
            padding: 0;
        }
        .rank-item {
            padding: 10px;
            margin: 5px 0;
            background: #f8f9fa;
            border-radius: 5px;
            display: flex;
            justify-content: space-between;
        }
        .rank-number {
            display: inline-block;
            width: 24px;
            height: 24px;
            background: #4CAF50;
            color: white;
            text-align: center;
            line-height: 24px;
            border-radius: 50%;
            margin-right: 10px;
        }
        .map-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 20px;
            overflow: hidden;
        }
        .map-wrapper {
            position: relative;
            width: 100%;
            padding-top: 42%;
            overflow: hidden;
        }
        .map-content {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
        }
        #world-map {
            width: 100%;
            height: 100%;
            background-image: url('/static/defaultMap.jpg');
            background-size: 100% 100%;
            background-repeat: no-repeat;
            background-position: center;
            position: relative;
        }
        .attack-point {
            fill: #ff4444;
            opacity: 0.6;
            transition: all 0.3s;
            filter: url(#glow);
        }
        .attack-point:hover {
            opacity: 1;
            cursor: pointer;
        }
        .tooltip {
            position: absolute;
            padding: 8px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            z-index: 1000;
            display: none;
            white-space: pre-line;
        }
        .trend-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 20px;
        }
        .trend-chart {
            width: 100%;
            padding: 20px 0;
            /* 移除 overflow-x: auto; 因为我们要让内容自适应宽度 */
        }
        .chart-wrapper {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            height: 200px;
            width: 100%;  /* 改为100%，不再使用 min-width */
            padding: 0 10px;
        }
        .bar-wrapper {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 20px;  /* 减小最小宽度，从30px改为20px */
            margin: 0 1px;    /* 减小边距，从2px改为1px */
        }
        .bar {
            width: 15px;      /* 减小柱子宽度，从20px改为15px */
            background-color: #4CAF50;
            border-radius: 2px 2px 0 0;
            transition: all 0.3s;
        }
        .hour-label {
            margin-top: 5px;
            font-size: 11px;   /* 稍微减小字体大小 */
            color: #666;
            transform: rotate(-45deg);
            transform-origin: top right;
            white-space: nowrap;
        }
        .trend-container {
            position: relative;  /* 添加这一行 */
        }

        .tooltip {
            position: fixed;
            padding: 8px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            z-index: 1000;
            display: none;
            white-space: pre-line;
            transform: translate(-50%, -100%);
        }

        .bar {
            cursor: pointer;  /* 添加这一行 */
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>是谁在敲打我窗</h1>
        <button class="refresh-btn" onclick="location.reload()">刷新</button>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <h3>总尝试次数</h3>
            <div class="stat-number">{{ stats.total_attempts }}</div>
        </div>
        <div class="stat-card">
            <h3>独立IP数量</h3>
            <div class="stat-number">{{ stats.unique_ips }}</div>
        </div>
        <div class="stat-card">
            <h3>尝试城市数量</h3>
            <div class="stat-number">{{ stats.unique_cities }}</div>
        </div>
    </div>

    <div class="map-container">
        <h2>全球尝试分布图</h2>
        <div class="map-wrapper">
            <div class="map-content">
                <div id="tooltip" class="tooltip"></div>
                <svg id="world-map" viewBox="0 0 360 180" preserveAspectRatio="xMidYMid meet">
                    <defs>
                        <filter id="glow">
                            <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                            <feMerge>
                                <feMergeNode in="coloredBlur"/>
                                <feMergeNode in="SourceGraphic"/>
                            </feMerge>
                        </filter>
                    </defs>
                </svg>
            </div>
        </div>
    </div>

    <div class="container">
        <div class="column">
            <h2>IP 地址排行榜</h2>
            <ul class="rank-list">
                {% for ip, city, count in stats.top_ips %}
                <li class="rank-item">
                    <span>
                        <span class="rank-number">{{ loop.index }}</span>
                        {{ ip }} ({{ city }})
                    </span>
                    <span>{{ count }}次</span>
                </li>
                {% endfor %}
            </ul>
        </div>
        <div class="column">
            <h2>城市排行榜</h2>
            <ul class="rank-list">
                {% for city, count in stats.top_cities %}
                <li class="rank-item">
                    <span>
                        <span class="rank-number">{{ loop.index }}</span>
                        {{ city }}
                    </span>
                    <span>{{ count }}次</span>
                </li>
                {% endfor %}
            </ul>
        </div>
    </div>

    <div class="trend-container">
        <h2>24小时趋势</h2>
        <div class="trend-chart">
            <div id="trend-tooltip" class="tooltip"></div>
            <div class="chart-wrapper">
                {% set max_count = stats.hourly_trend|map(attribute='count')|max %}
                {% set height_factor = 180 %}
                {% for item in stats.hourly_trend %}
                    {% if max_count > 0 %}
                        {% set bar_height = (item.count / max_count * height_factor)|round %}
                    {% else %}
                        {% set bar_height = 0 %}
                    {% endif %}
                    <div class="bar-wrapper">
                        <div class="bar" 
                             style="height: {{ bar_height }}px;"
                             data-hour="{{ item.hour }}"
                             data-count="{{ item.count }}">
                        </div>
                        <div class="hour-label">{{ item.hour }}</div>
                    </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <script>
        function normalizeCoordinates(lon, lat) {
            const mapWidth = 360;
            const mapHeight = 180;
            
            // 调整经度缩放比例为1.2
            const x = ((parseFloat(lon) * 1.2 + 180) / 360) * mapWidth;
            const y = ((90 - parseFloat(lat)) / 180) * mapHeight;
            
            return { x, y };
        }

        function updateMap() {
            const tooltip = document.getElementById('tooltip');
            const svg = document.getElementById('world-map');
            
            fetch('/api/map_data')
                .then(response => response.json())
                .then(data => {
                    document.querySelectorAll('.attack-point').forEach(el => el.remove());
                    
                    data.forEach(point => {
                        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                        const coords = normalizeCoordinates(point.lon, point.lat);
                        
                        circle.setAttribute('cx', coords.x);
                        circle.setAttribute('cy', coords.y);
                        
                        const radius = Math.log(point.count + 1) * 1.5;
                        circle.setAttribute('r', radius);
                        circle.setAttribute('class', 'attack-point');
                        
                        // 修改后的提示框定位逻辑
                        // 修改 mousemove 事件处理函数
                    circle.addEventListener('mousemove', (e) => {
                        const rect = svg.getBoundingClientRect();
                        const scale = rect.width / svg.viewBox.baseVal.width;
    
                        // 计算相对于SVG的坐标
                        const x = e.clientX - rect.left;
                        const y = e.clientY - rect.top;
    
                        tooltip.style.display = 'block';
                        // 根据圆点位置定位提示框
                        tooltip.style.left = (x + 10) + 'px';  // 向右偏移10px
                        tooltip.style.top = (y - 5) + 'px';    // 向上偏移5px
    
                        let tooltipText = `${point.city}: ${point.count}次攻击`;
                        if (point.country) {
                            tooltipText += `\n国家/地区: ${point.country}`;
                        }
                        if (point.admin_area) {
                            tooltipText += `\n省/州: ${point.admin_area}`;
                        }
                        tooltip.textContent = tooltipText;
                    });
                        
                        circle.addEventListener('mouseout', () => {
                            tooltip.style.display = 'none';
                        });
                        
                        svg.appendChild(circle);
                    });
                })
                .catch(error => {
                    console.error('Error updating map:', error);
                });
        }

        updateMap();
        setInterval(updateMap, 30000);
        window.addEventListener('resize', updateMap);

        document.addEventListener('DOMContentLoaded', function() {
            const trendTooltip = document.getElementById('trend-tooltip');
            const bars = document.querySelectorAll('.bar');
    
            bars.forEach(bar => {
                bar.addEventListener('mousemove', (e) => {
                    const hour = bar.getAttribute('data-hour');
                    const count = bar.getAttribute('data-count');
            
                    trendTooltip.textContent = `${hour}: ${count}次尝试`;
                    trendTooltip.style.display = 'block';
            
                    // 计算提示框位置
                    const rect = bar.getBoundingClientRect();
                    const tooltipX = rect.left + (rect.width / 2);
                    const tooltipY = rect.top - 10;
            
                    trendTooltip.style.left = tooltipX + 'px';
                    trendTooltip.style.top = tooltipY + 'px';
                });
        
                bar.addEventListener('mouseout', () => {
                    trendTooltip.style.display = 'none';
                });
            });
        });
    </script>

    <div style="text-align: center; margin-top: 20px; color: #666;">
        最后更新时间: {{ current_time }}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    stats = get_stats()
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template_string(HTML_TEMPLATE, stats=stats, current_time=current_time)

def init_app():
    """初始化应用程序"""
    os.makedirs('static', exist_ok=True)
    
    if not os.path.exists('static/defaultMap.jpg'):
        print("Warning: Map file not found at static/defaultMap.jpg")
        
    GeoData()

if __name__ == '__main__':
    init_app()
    app.run(host='0.0.0.0', port=5000)