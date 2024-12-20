import socket
import threading
import datetime
import json
from pathlib import Path
import paramiko
import requests
import time
from typing import Optional, Dict, Any
from flask import Flask, render_template_string, jsonify, request
from collections import Counter
from datetime import timedelta
import os

# Flask应用初始化
app = Flask(__name__)
app.static_folder = 'static'

# 确保static目录存在
os.makedirs('static', exist_ok=True)

# 预定义主要城市的坐标和国家信息
KNOWN_LOCATIONS = {
    "Moscow": {"lat": 55.7558, "lon": 37.6173, "country": "Russia", "admin_area": "Moscow"},
    "Taichung": {"lat": 24.144, "lon": 120.6844, "country": "China", "admin_area": "Taiwan"},
    "Taipei": {"lat": 25.0289, "lon": 121.521, "country": "China", "admin_area": "Taiwan"},
    "New Taipei City": {"lat": 25.062, "lon": 121.457, "country": "China", "admin_area": "Taiwan"},
    "Kaohsiung": {"lat": 22.6148, "lon": 120.3139, "country": "China", "admin_area": "Taiwan"},
    "Tainan": {"lat": 22.9908, "lon": 120.2133, "country": "China", "admin_area": "Taiwan"},
    "Hsinchu": {"lat": 24.8036, "lon": 120.9686, "country": "China", "admin_area": "Taiwan"}, 
    "Keelung": {"lat": 25.1283, "lon": 121.7419, "country": "China", "admin_area": "Taiwan"},
    "Chiayi": {"lat": 23.4800, "lon": 120.4491, "country": "China", "admin_area": "Taiwan"},
    "Changhua": {"lat": 24.0734, "lon": 120.5134, "country": "China", "admin_area": "Taiwan"},
    "Taoyuan": {"lat": 24.9937, "lon": 121.3010, "country": "China", "admin_area": "Taiwan"},
    "Pingtung": {"lat": 22.6762, "lon": 120.4929, "country": "China", "admin_area": "Taiwan"},
    "Yilan": {"lat": 24.7570, "lon": 121.7533, "country": "China", "admin_area": "Taiwan"},
    "Hualien": {"lat": 23.9910, "lon": 121.6111, "country": "China", "admin_area": "Taiwan"},
    "Taitung": {"lat": 22.7583, "lon": 121.1444, "country": "China", "admin_area": "Taiwan"},
    "Miaoli": {"lat": 24.5657, "lon": 120.8214, "country": "China", "admin_area": "Taiwan"},
    "Nantou": {"lat": 23.9157, "lon": 120.6869, "country": "China", "admin_area": "Taiwan"}
}

COUNTRY_INFO = {
    "Moscow": "Russia"
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

class SSHMonitor(paramiko.ServerInterface):
    def __init__(self, host='0.0.0.0', port=22):
        self.host = host
        self.port = port
        self.ssh_log_file = Path('ssh_attempts.json')
        self.city_data_file = Path('city_data.json')
        self.geo_data_file = Path('geo_data.json')
        
        # 初始化或加载数据文件
        self.attempts = self._load_json(self.ssh_log_file, [])
        self.city_data = self._load_json(self.city_data_file, {})
        self.geo_data = self._load_json(self.geo_data_file, {})
        
        # 生成服务器密钥
        self.key = paramiko.RSAKey.generate(2048)

    def _load_json(self, file_path: Path, default: Any) -> Any:
        """加载JSON文件，如果文件不存在则返回默认值"""
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return default

    def _save_json(self, file_path: Path, data: Any) -> None:
        """保存数据到JSON文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _get_location_data(self, ip: str) -> Optional[Dict]:
        """获取IP地址的地理位置信息"""
        if ip in self.city_data:
            city = self.city_data[ip]
            return {"city": city}

        try:
            url = f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,lat,lon"
            response = requests.get(url)
            data = response.json()
            
            if data["status"] != "success":
                return None

            self.city_data[ip] = data["city"]
            self._save_json(self.city_data_file, self.city_data)

            if data["city"] not in self.geo_data:
                self.geo_data[data["city"]] = {
                    "lat": data["lat"],
                    "lon": data["lon"],
                    "country": data["country"],
                    "admin_area": data["regionName"],
                    "last_updated": datetime.datetime.now().isoformat()
                }
                self._save_json(self.geo_data_file, self.geo_data)

            return {
                "city": data["city"]
            }

        except Exception as e:
            print(f"Error getting location data for IP {ip}: {e}")
            return None

    def check_auth_password(self, username: str, password: str) -> int:
        """记录认证尝试并拒绝"""
        time.sleep(4)
        
        location_data = self._get_location_data(self.client_ip)
        if location_data is None:
            return paramiko.AUTH_FAILED

        attempt = {
            "timestamp": datetime.datetime.now().isoformat(),
            "ip": self.client_ip,
            "password": password,
            "city": location_data["city"]
        }
        
        self.attempts.append(attempt)
        self._save_json(self.ssh_log_file, self.attempts)
        
        print(f"记录登录尝试 - IP: {self.client_ip}, 城市: {location_data['city']}")
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username: str) -> str:
        """允许密码认证"""
        return 'password'

    def _handle_connection(self, client_socket: socket.socket, address: tuple) -> None:
        """处理单个连接"""
        try:
            self.client_ip = address[0]
            self.client_port = address[1]
            
            transport = paramiko.Transport(client_socket)
            transport.add_server_key(self.key)
            transport.start_server(server=self)
            
            channel = transport.accept(20)
            if channel is not None:
                channel.close()

        except Exception as e:
            print(f"处理连接时出错: {e}")
        finally:
            try:
                transport.close()
            except:
                pass
            client_socket.close()

    def start(self) -> None:
        """启动SSH监控服务器"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(5)
        
        print(f"开始监控SSH尝试，监听地址 {self.host}:{self.port}")
        
        try:
            while True:
                client, address = server.accept()
                thread = threading.Thread(
                    target=self._handle_connection,
                    args=(client, address)
                )
                thread.daemon = True
                thread.start()
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n正在关闭监控...")
        finally:
            server.close()

def load_attempts():
    """加载SSH尝试记录"""
    try:
        with open('ssh_attempts.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def get_stats(time_range='all'):
    """获取统计数据"""
    attempts = load_attempts()
    
    if time_range == '24h':
        now = datetime.datetime.now()
        twenty_four_hours_ago = now - timedelta(hours=24)
        attempts = [attempt for attempt in attempts if datetime.datetime.fromisoformat(attempt['timestamp']) >= twenty_four_hours_ago]
    
    ip_counts = Counter()
    city_counts = Counter()
    country_counts = Counter()  # 新增国家计数器
    hourly_counts = Counter()
    now = datetime.datetime.now()
    twenty_four_hours_ago = now - timedelta(hours=24)
    
    ip_city_map = {}
    
    for attempt in attempts:
        ip = attempt['ip']
        city = attempt.get('city', 'Unknown')
        ip_city_map[ip] = city
        
        # 获取国家信息并计数
        geo = GeoData()
        location = geo.get_city_location(city)
        if location and 'country' in location:
            country = location['country']
            country_counts[country] += 1
            
        try:
            timestamp = datetime.datetime.fromisoformat(attempt['timestamp'])
            if timestamp >= twenty_four_hours_ago:
                hour = timestamp.strftime('%H:00')
                hourly_counts[hour] += 1
        except:
            pass
            
        ip_counts[ip] += 1
        city_counts[city] += 1

    top_ips = [(ip, ip_city_map[ip], count) for ip, count in ip_counts.most_common(10)]
    top_cities = city_counts.most_common(10)
    
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
        'unique_cities': len(city_counts),
        'unique_countries': len(country_counts)  # 新增返回国家数量
    }

@app.route('/api/map_data')
def map_data():
    """提供地图数据API"""
    time_range = request.args.get('time_range', 'all')
    geo = GeoData()
    attempts = load_attempts()
    
    if time_range == '24h':
        now = datetime.datetime.now()
        twenty_four_hours_ago = now - timedelta(hours=24)
        attempts = [attempt for attempt in attempts if datetime.datetime.fromisoformat(attempt['timestamp']) >= twenty_four_hours_ago]
    
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

# HTML模板内容
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>是谁在敲打我窗</title>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="30">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
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
            grid-template-columns: repeat(4, 1fr);
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
            max-width: 200px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .trend-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 20px;
            position: relative;
        }
        .trend-chart {
            width: 100%;
            padding: 20px 0;
        }
        .chart-wrapper {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            height: 200px;
            width: 100%;
            padding: 0 10px;
        }
        .bar-wrapper {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 20px;
            margin: 0 1px;
        }
        .bar {
            width: 15px;
            background-color: #4CAF50;
            border-radius: 2px 2px 0 0;
            transition: all 0.3s;
            cursor: pointer;
        }
        .hour-label {
            margin-top: 5px;
            font-size: 11px;
            color: #666;
            transform: rotate(-45deg);
            transform-origin: top right;
            white-space: nowrap;
        }
        #loading-indicator {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 15px 30px;
            border-radius: 5px;
            display: none;
            z-index: 1000;
        }
    </style>
</head>
<body>
    <div id="loading-indicator">正在加载数据...</div>
    <div class="header">
        <h1>是谁在敲打我窗</h1>
        <div>
            <select id="time-range">
                <option value="all">全部</option>
                <option value="24h">24小时</option>
            </select>
            <button class="refresh-btn" onclick="refreshData()">刷新</button>
        </div>
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
        <div class="stat-card">
            <h3>尝试国家数量</h3>
            <div class="stat-number">{{ stats.unique_countries }}</div>
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
        // 获取当前时间范围
        function getCurrentTimeRange() {
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get('time_range') || 'all';
        }

        // 显示加载指示器
        function showLoading() {
            document.getElementById('loading-indicator').style.display = 'block';
        }

        // 隐藏加载指示器
        function hideLoading() {
            document.getElementById('loading-indicator').style.display = 'none';
        }

        function normalizeCoordinates(lon, lat) {
            const mapWidth = 360;
            const mapHeight = 180;
            const x = ((parseFloat(lon) * 1.2 + 180) / 360) * mapWidth;
            const y = ((90 - parseFloat(lat)) / 180) * mapHeight;
            return { x, y };
        }

        // 更新地图数据
        function updateMap() {
            showLoading();
            const tooltip = document.getElementById('tooltip');
            const svg = document.getElementById('world-map');
            const timeRange = getCurrentTimeRange();
            
            fetch(`/api/map_data?time_range=${timeRange}`)
                .then(response => response.json())
                .then(data => {
                    // 清除现有点
                    document.querySelectorAll('.attack-point').forEach(el => el.remove());
                    
                    // 添加新的点
                    data.forEach(point => {
                        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                        const coords = normalizeCoordinates(point.lon, point.lat);
                        
                        circle.setAttribute('cx', coords.x);
                        circle.setAttribute('cy', coords.y);
                        
                        const radius = Math.log(point.count + 1) * 1.5;
                        circle.setAttribute('r', radius);
                        circle.setAttribute('class', 'attack-point');
                        
                        circle.addEventListener('mousemove', (e) => {
                            const rect = svg.getBoundingClientRect();
                            const scale = rect.width / svg.viewBox.baseVal.width;
                            
                            // 获取圆点在页面上的实际位置
                            const circleX = rect.left + (coords.x * scale);
                            const circleY = rect.top + (coords.y * scale);
                            
                            tooltip.style.display = 'block';
                            
                            // 计算提示框位置
                            let tooltipX = circleX + (radius * scale) + 10;
                            let tooltipY = circleY - 10;
                            
                            // 检查是否会超出右边界
                            if (tooltipX + tooltip.offsetWidth > window.innerWidth) {
                                tooltipX = circleX - tooltip.offsetWidth - 10;
                            }
                            
                            // 检查是否会超出上边界
                            if (tooltipY < 0) {
                                tooltipY = circleY + 20;
                            }
                            
                            tooltip.style.left = tooltipX + 'px';
                            tooltip.style.top = tooltipY + 'px';
                            
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
                    hideLoading();
                })
                .catch(error => {
                    console.error('Error updating map:', error);
                    hideLoading();
                });
        }

        // 刷新所有数据
        function refreshData() {
            const timeRange = getCurrentTimeRange();
            window.location.href = `/?time_range=${timeRange}`;
        }

        // 初始化页面
        document.addEventListener('DOMContentLoaded', function() {
            const timeRange = getCurrentTimeRange();
            document.getElementById('time-range').value = timeRange;

            // 设置时间范围选择器的事件处理
            document.getElementById('time-range').addEventListener('change', function() {
                const selectedTimeRange = this.value;
                window.location.href = `/?time_range=${selectedTimeRange}`;
            });

            // 设置趋势图工具提示
            const trendTooltip = document.getElementById('trend-tooltip');
            const bars = document.querySelectorAll('.bar');
            
            bars.forEach(bar => {
                bar.addEventListener('mousemove', (e) => {
                    const hour = bar.getAttribute('data-hour');
                    const count = bar.getAttribute('data-count');
                    
                    trendTooltip.textContent = `${hour}: ${count}次尝试`;
                    trendTooltip.style.display = 'block';
                    
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

            // 初始更新地图
            updateMap();
        });

        // 定期更新地图
        setInterval(updateMap, 30000);
        
        // 响应窗口大小变化
        window.addEventListener('resize', updateMap);
    </script>

    <div style="text-align: center; margin-top: 20px; color: #666; display: flex; justify-content: center; align-items: center; gap: 20px;">
        <span>最后更新时间: {{ current_time }}</span>
        <a href="https://github.com/Yorkian/knock" target="_blank" style="color: #666; text-decoration: none; font-size: 24px;">
            <i class="bi bi-github"></i>
        </a>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    """首页路由"""
    time_range = request.args.get('time_range', 'all')
    stats = get_stats(time_range)
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template_string(HTML_TEMPLATE, stats=stats, current_time=current_time)

def init_app():
    """初始化应用程序"""
    os.makedirs('static', exist_ok=True)
    
    if not os.path.exists('static/defaultMap.jpg'):
        print("Warning: Map file not found at static/defaultMap.jpg")
        
    GeoData()

def main():
    """主程序入口"""
    # 初始化SSH监控器
    ssh_monitor = SSHMonitor(port=22)
    
    # 启动SSH监控器线程
    monitor_thread = threading.Thread(target=ssh_monitor.start)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # 初始化Flask应用
    init_app()
    
    # 启动Web服务器
    try:
        app.run(host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n正在关闭服务...")
    except Exception as e:
        print(f"服务器运行出错: {e}")

if __name__ == '__main__':
    main()