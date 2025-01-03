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

# Language translations
TRANSLATIONS = {
    'en': {
        'title': 'Who is Knocking at My Window',
        'refresh': 'Refresh',
        'total_attempts': 'Total Attempts',
        'unique_ips': 'Unique IPs',
        'attempt_cities': 'Attempt Cities',
        'attempt_countries': 'Attempt Countries',
        'global_distribution': 'Global Distribution',
        'ip_ranking': 'IP Address Ranking',
        'city_ranking': 'City Ranking',
        'hour_trend': '24-Hour Trend',
        'attempts': ' attempts',
        'loading': 'Loading data...',
        'last_update': 'Last Update',
        'time_range_all': 'All',
        'time_range_24h': '24h',
        'attack_times': 'attacks',
        'country_region': 'Country',
        'province_state': 'Province/State',
        'switch_to_24h': '24h',
        'switch_to_all': 'All',
        'switch_to_zh': '中文',
        'switch_to_en': 'English',
        'attempt_times': ' attempts'
    },
    'zh': {
        'title': '是谁在敲打我窗',
        'refresh': '刷新',
        'total_attempts': '总尝试次数',
        'unique_ips': '独立IP数量',
        'attempt_cities': '尝试城市数量',
        'attempt_countries': '尝试国家数量',
        'global_distribution': '全球尝试分布图',
        'ip_ranking': 'IP 地址排行榜',
        'city_ranking': '城市排行榜',
        'hour_trend': '24小时趋势',
        'attempts': '次',
        'loading': '正在加载数据...',
        'last_update': '最后更新时间',
        'time_range_all': '全部',
        'time_range_24h': '24小时',
        'attack_times': '次攻击',
        'country_region': '国家',
        'province_state': '省/州',
        'switch_to_24h': '24小时',
        'switch_to_all': '全部',
        'switch_to_zh': '中文',
        'switch_to_en': 'English',
        'attempt_times': '次尝试'
    }
}

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
        # 添加缓存命中记录集合
        self.cache_hits = set()

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
        # 对于同一个实例，每个城市只打印一次缓存命中信息
        if city in KNOWN_LOCATIONS:
            if city not in self.cache_hits:
                print(f"Using predefined location for {city}")
                self.cache_hits.add(city)
            return KNOWN_LOCATIONS[city]
            
        if city in self.geo_data:
            if city not in self.cache_hits:
                print(f"Using cached data for {city}")
                self.cache_hits.add(city)
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
        
        # 添加连接计数器
        self.connection_count = 0
        self.last_cleanup = time.time()

    def _load_json(self, file_path: Path, default_value: Any) -> Any:
        """加载JSON文件，如果文件不存在或无效则返回默认值"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return default_value
        except json.JSONDecodeError as e:
            print(f"Error loading {file_path}: {e}")
            return default_value
        except Exception as e:
            print(f"Unexpected error loading {file_path}: {e}")
            return default_value

    def _save_json(self, file_path: Path, data: Any) -> None:
        """保存数据到JSON文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving to {file_path}: {e}")

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
        
        print(f"Trying - IP: {self.client_ip}, City: {location_data['city']}")
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username: str) -> str:
        """允许密码认证"""
        return 'password'

    def _handle_connection(self, client_socket: socket.socket, address: tuple) -> None:
            """处理单个连接"""
            transport = None
            try:
                self.client_ip = address[0]
                self.client_port = address[1]
                
                # 设置客户端 socket 的超时时间
                client_socket.settimeout(10)
                
                transport = paramiko.Transport(client_socket)
                transport.local_version = "SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.1"
                transport.add_server_key(self.key)
                
                try:
                    # 移除不支持的 timeout 参数
                    transport.start_server(server=self)
                except paramiko.SSHException as e:
                    if "Error reading SSH protocol banner" in str(e):
                        print(f"Client {self.client_ip} failed to send SSH banner")
                        return
                    raise
                    
                # 设置通道接受的超时时间
                channel = transport.accept(timeout=5)
                if channel is not None:
                    channel.close()

            except socket.timeout:
                print(f"Connection from {self.client_ip} timed out")
            except ConnectionResetError:
                print(f"Connection reset by {self.client_ip}")
            except Exception as e:
                error_type = type(e).__name__
                if error_type not in ['SSHException', 'socket.timeout', 'ConnectionResetError']:
                    print(f"Unexpected error handling connection from {self.client_ip}: {error_type}: {str(e)}")
            finally:
                if transport:
                    try:
                        transport.close()
                    except:
                        pass
                try:
                    client_socket.close()
                except:
                    pass
                
                self.connection_count += 1
                
                if self.connection_count % 1000 == 0:
                    self._cleanup()

    def _cleanup(self):
        """定期清理和维护"""
        current_time = time.time()
        if current_time - self.last_cleanup > 3600:
            import gc
            gc.collect()
            self.last_cleanup = current_time

    def start(self) -> None:
        """启动SSH监控服务器"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.settimeout(1)
        
        server.bind((self.host, self.port))
        server.listen(5)
        
        print(f"开始监控SSH尝试，监听地址 {self.host}:{self.port}")
        
        while True:
            try:
                client, address = server.accept()
                thread = threading.Thread(
                    target=self._handle_connection,
                    args=(client, address)
                )
                thread.daemon = True
                thread.start()
                
                time.sleep(0.1)
                
            except socket.timeout:
                continue
            except KeyboardInterrupt:
                print("\n正在关闭监控...")
                break
            except Exception as e:
                print(f"接受连接时出错: {e}")
                time.sleep(1)
                
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
    
    # 如果时间范围是24小时，过滤数据
    if time_range == '24h':
        now = datetime.datetime.now()
        twenty_four_hours_ago = now - timedelta(hours=24)
        attempts = [attempt for attempt in attempts if datetime.datetime.fromisoformat(attempt['timestamp']) >= twenty_four_hours_ago]
    
    # 在循环外创建单个 GeoData 实例
    geo = GeoData()
    
    # 初始化计数器
    ip_counts = Counter()
    city_counts = Counter()
    country_counts = Counter()
    hourly_counts = Counter()
    now = datetime.datetime.now()
    twenty_four_hours_ago = now - timedelta(hours=24)
    
    ip_city_map = {}
    
    # 处理每条记录
    for attempt in attempts:
        ip = attempt['ip']
        city = attempt.get('city', 'Unknown')
        ip_city_map[ip] = city
        
        # 获取地理位置信息
        location = geo.get_city_location(city)
        if location and 'country' in location:
            country = location['country']
            country_counts[country] += 1
            
        # 处理时间趋势数据
        try:
            timestamp = datetime.datetime.fromisoformat(attempt['timestamp'])
            if timestamp >= twenty_four_hours_ago:
                hour = timestamp.strftime('%H:00')
                hourly_counts[hour] += 1
        except:
            pass
            
        ip_counts[ip] += 1
        city_counts[city] += 1

    # 获取排名前10的IP
    top_ips = [(ip, ip_city_map[ip], count) for ip, count in ip_counts.most_common(10)]
    # 获取排名前10的城市
    top_cities = city_counts.most_common(10)
    
    # 生成24小时趋势数据
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

    # 返回统计结果
    return {
        'top_ips': top_ips,
        'top_cities': top_cities,
        'hourly_trend': hours,
        'total_attempts': len(attempts),
        'unique_ips': len(ip_counts),
        'unique_cities': len(city_counts),
        'unique_countries': len(country_counts)
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
    <title>{{ t.title }}</title>
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
        .language-selector {
            margin-left: 10px;
            padding: 8px 15px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .language-selector:hover {
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
        .button-group {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .custom-button {
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
            font-size: 14px;
            min-width: 100px;
            text-align: center;
        }
        
        .custom-button:hover {
            background-color: #45a049;
        }
        
        .custom-button.active {
            background-color: #357a38;
        }
    </style>
</head>
<body>
    <div id="loading-indicator">{{ t.loading }}</div>
    <div class="header">
        <h1>{{ t.title }}</h1>
        <div class="button-group">
            <button class="custom-button" onclick="refreshData()">{{ t.refresh }}</button>
            <button class="custom-button" id="timeRangeToggle" onclick="toggleTimeRange()">
                {% if time_range == 'all' %}
                    {{ t.switch_to_24h }}
                {% else %}
                    {{ t.switch_to_all }}
                {% endif %}
            </button>
            <button class="custom-button" onclick="toggleLanguage()">
                {% if lang == 'en' %}
                    {{ t.switch_to_zh }}
                {% else %}
                    {{ t.switch_to_en }}
                {% endif %}
            </button>
        </div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <h3>{{ t.total_attempts }}</h3>
            <div class="stat-number">{{ stats.total_attempts }}</div>
        </div>
        <div class="stat-card">
            <h3>{{ t.unique_ips }}</h3>
            <div class="stat-number">{{ stats.unique_ips }}</div>
        </div>
        <div class="stat-card">
            <h3>{{ t.attempt_cities }}</h3>
            <div class="stat-number">{{ stats.unique_cities }}</div>
        </div>
        <div class="stat-card">
            <h3>{{ t.attempt_countries }}</h3>
            <div class="stat-number">{{ stats.unique_countries }}</div>
        </div>
    </div>

    <div class="map-container">
        <h2>{{ t.global_distribution }}</h2>
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
            <h2>{{ t.ip_ranking }}</h2>
            <ul class="rank-list">
                {% for ip, city, count in stats.top_ips %}
                <li class="rank-item">
                    <span>
                        <span class="rank-number">{{ loop.index }}</span>
                        {{ ip }} ({{ city }})
                    </span>
                    <span>{{ count }}{{ t.attempts }}</span>
                </li>
                {% endfor %}
            </ul>
        </div>
        <div class="column">
            <h2>{{ t.city_ranking }}</h2>
            <ul class="rank-list">
                {% for city, count in stats.top_cities %}
                <li class="rank-item">
                    <span>
                        <span class="rank-number">{{ loop.index }}</span>
                        {{ city }}
                    </span>
                    <span>{{ count }}{{ t.attempts }}</span>
                </li>
                {% endfor %}
            </ul>
        </div>
    </div>


    <div class="trend-container">
        <h2>{{ t.hour_trend }}</h2>
        <div class="trend-chart">
            <div id="trend-tooltip" class="tooltip"></div>
            <div class="chart-wrapper">
                {% set max_count = namespace(value=0) %}
                {% for item in stats.hourly_trend %}
                    {% if item.count > max_count.value %}
                        {% set max_count.value = item.count %}
                    {% endif %}
                {% endfor %}
                
                {% set height_factor = 180 %}
                {% for item in stats.hourly_trend %}
                    {% set height = 0 %}
                    {% if max_count.value > 0 %}
                        {% set height = (item.count / max_count.value * height_factor)|round|int %}
                    {% endif %}
                    <div class="bar-wrapper">
                        <div class="bar" 
                             style="height: {{ height }}px;"
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
        // Get current time range
        function getCurrentTimeRange() {
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get('time_range') || 'all';
        }

        // Get current language
        function getCurrentLanguage() {
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get('lang') || 'en';  // Default to English
        }

        // Get button text based on current state
        function getTimeRangeButtonText(currentTimeRange, lang) {
            if (currentTimeRange === 'all') {
                return lang === 'zh' ? '24小时' : '24h';
            }
            return lang === 'zh' ? '全部' : 'All';
        }

        function getLanguageButtonText(currentLang) {
            return currentLang === 'en' ? '中文' : 'English';
        }

        // Toggle time range
        function toggleTimeRange() {
            const currentTimeRange = getCurrentTimeRange();
            const newTimeRange = currentTimeRange === 'all' ? '24h' : 'all';
            const lang = getCurrentLanguage();
            window.location.href = `/?lang=${lang}&time_range=${newTimeRange}`;
        }

        // Toggle language
        function toggleLanguage() {
            const currentLang = getCurrentLanguage();
            const newLang = currentLang === 'en' ? 'zh' : 'en';
            const timeRange = getCurrentTimeRange();
            window.location.href = `/?lang=${newLang}&time_range=${timeRange}`;
        }

        // Show loading indicator
        function showLoading() {
            document.getElementById('loading-indicator').style.display = 'block';
        }

        // Hide loading indicator
        function hideLoading() {
            document.getElementById('loading-indicator').style.display = 'none';
        }

        // Normalize coordinates for map
        function normalizeCoordinates(lon, lat) {
            const mapWidth = 360;
            const mapHeight = 180;
            const x = ((parseFloat(lon) * 1.2 + 180) / 360) * mapWidth;
            const y = ((90 - parseFloat(lat)) / 180) * mapHeight;
            return { x, y };
        }

        // Refresh all data
        function refreshData() {
            const timeRange = getCurrentTimeRange();
            const lang = getCurrentLanguage();
            window.location.href = `/?lang=${lang}&time_range=${timeRange}`;
        }

        // Update map data
        function updateMap() {
            showLoading();
            const tooltip = document.getElementById('tooltip');
            const svg = document.getElementById('world-map');
            const timeRange = getCurrentTimeRange();
            const lang = getCurrentLanguage();
            
            fetch(`/api/map_data?time_range=${timeRange}`)
                .then(response => response.json())
                .then(data => {
                    // Clear existing points
                    document.querySelectorAll('.attack-point').forEach(el => el.remove());
                    
                    // Add new points
                    data.forEach(point => {
                        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                        const coords = normalizeCoordinates(point.lon, point.lat);
                        
                        circle.setAttribute('cx', coords.x);
                        circle.setAttribute('cy', coords.y);
                        
                        const radius = Math.log(point.count + 1) * 1.5;
                        circle.setAttribute('r', radius);
                        circle.setAttribute('class', 'attack-point');
                        
                        circle.addEventListener('mousemove', (e) => {
                            const translations = {
                                'zh': {
                                    'attack_times': '次攻击',
                                    'country_region': '国家/地区',
                                    'province_state': '省/州'
                                },
                                'en': {
                                    'attack_times': 'attacks',
                                    'country_region': 'Country/Region',
                                    'province_state': 'Province/State'
                                }
                            };
                            
                            const t = translations[lang];
                            
                            tooltip.style.display = 'block';
                            
                            let tooltipText = `${point.city}: ${point.count} ${t.attack_times}`;
                            if (point.country) {
                                tooltipText += `\n${t.country_region}: ${point.country}`;
                            }
                            if (point.admin_area) {
                                tooltipText += `\n${t.province_state}: ${point.admin_area}`;
                            }
                            tooltip.textContent = tooltipText;
                            
                            // Position tooltip
                            let tooltipX = e.pageX + 10;
                            let tooltipY = e.pageY - 10;
                            
                            if (tooltipX + tooltip.offsetWidth > window.innerWidth) {
                                tooltipX = e.pageX - tooltip.offsetWidth - 10;
                            }
                            
                            tooltip.style.left = tooltipX + 'px';
                            tooltip.style.top = tooltipY + 'px';
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

        // Initialize page
        document.addEventListener('DOMContentLoaded', function() {
            const timeRange = getCurrentTimeRange();
            const lang = getCurrentLanguage();
            
            // Update button texts
            const timeRangeButton = document.getElementById('timeRangeToggle');
            const languageButton = document.querySelector('.button-group button:last-child');
            
            // Set initial button texts to show target states
            timeRangeButton.textContent = getTimeRangeButtonText(timeRange, lang);
            languageButton.textContent = getLanguageButtonText(lang);
            
            // Initialize trend chart tooltips
            const trendTooltip = document.getElementById('trend-tooltip');
            const bars = document.querySelectorAll('.bar');
            
            bars.forEach(bar => {
                bar.addEventListener('mousemove', (e) => {
                    const hour = bar.getAttribute('data-hour');
                    const count = bar.getAttribute('data-count');
                    const attemptText = lang === 'zh' ? '次尝试' : 'attempts';
                    
                    trendTooltip.textContent = `${hour}: ${count} ${attemptText}`;
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

            // Initial map update
            updateMap();
        });

        // Update map periodically
        setInterval(updateMap, 30000);
        
        // Handle window resize
        window.addEventListener('resize', updateMap);
    </script>

    <div style="text-align: center; margin-top: 20px; color: #666; display: flex; justify-content: center; align-items: center; gap: 20px;">
        <span>{{ t.last_update }}: {{ current_time }}</span>
        <a href="https://github.com/Yorkian/knock" target="_blank" style="color: #666; text-decoration: none; font-size: 24px;">
            <i class="bi bi-github"></i>
        </a>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    """Homepage route with language support"""
    time_range = request.args.get('time_range', 'all')
    lang = request.args.get('lang', 'en')
    if lang not in TRANSLATIONS:
        lang = 'en'
    
    stats = get_stats(time_range)
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template_string(
        HTML_TEMPLATE,
        stats=stats,
        current_time=current_time,
        t=TRANSLATIONS[lang],
        lang=lang,
        time_range=time_range
    )


def init_app():
    """Initialize application"""
    os.makedirs('static', exist_ok=True)
    
    if not os.path.exists('static/defaultMap.jpg'):
        print("Warning: Map file not found at static/defaultMap.jpg")
        
    GeoData()

def main():
    """Main program entry"""
    # Initialize SSH monitor
    ssh_monitor = SSHMonitor(port=22)
    
    # Start SSH monitor thread
    monitor_thread = threading.Thread(target=ssh_monitor.start)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Initialize Flask application
    init_app()
    
    # Start web server
    try:
        app.run(host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\nShutting down service...")
    except Exception as e:
        print(f"Server error: {e}")

if __name__ == '__main__':
    main()
